"""Observation-only baselines. No evaluator, generator, environment or file access.

These are deterministic development baselines, not a security sandbox or learned
agents. Money conversion is the same public arithmetic primitive as the contract.
"""

from collections import defaultdict
from datetime import datetime
import random
from zoneinfo import ZoneInfo

from genesis_fintech.domain.money import convert_minor

FAMILIES = ("duplicate_invoice", "payment_allocation", "fx_mismatch", "period_cutoff")


class PagedPolicy:
    """Collect public pages, reserving a step for a bounded final submission."""

    def reset(self, observation):
        self.manifest = observation["manifest"]
        self.rules = observation["policy"]
        self.tables = {name: [] for name in ("invoices", "payments", "ledger", "fx")}
        self.queue = list(self.tables)
        self.pending = None
        self.cursor = None
        self.complete = False

    def act(self, observation):
        if self.pending is not None:
            if "error" in observation:
                # Partial data cannot justify reconciliation findings.
                return self.submit([])
            result = observation["result"]
            self.tables[self.pending].extend(result["records"])
            self.cursor = result["next_cursor"]
            if self.cursor is None:
                self.queue.pop(0)
            self.pending = None
        self.complete = not self.queue
        if self.complete:
            return self.submit(self.findings())
        if observation["remaining_steps"] <= 1:
            return self.submit([])
        self.pending = self.queue[0]
        return {"action": "list_records", "params": {
            "table": self.pending, "cursor": self.cursor, "limit": 50}}

    def submit(self, findings):
        return {"action": "submit", "params": {
            "episode_id": self.manifest["episode_id"], "findings": findings[:30]}}

    def finding(self, family, affected, amount, evidence, explanation):
        return {"type": family, "affected_ids": sorted(set(affected)),
                "claimed_amount_minor": amount, "currency": self.manifest["base_currency"],
                "evidence_ids": sorted(set(evidence))[:10], "explanation": explanation}

    def invoice_rows(self):
        rows = defaultdict(list)
        for row in self.tables["ledger"]:
            if row["payment_id"] is None:
                rows[row["invoice_id"]].append(row)
        return rows


class FlagAllPolicy(PagedPolicy):
    """Bounded attack baseline: accuse the first 30 invoices of duplication."""

    def findings(self):
        rows = self.invoice_rows()
        return [self.finding("duplicate_invoice", [invoice["invoice_id"]], invoice["total_minor"],
                             [invoice["doc_id"]] + [r["row_id"] for r in rows[invoice["invoice_id"]]],
                             "Flag-all baseline: unverified duplicate allegation.")
                for invoice in sorted(self.tables["invoices"], key=lambda r: r["invoice_id"])[:30]]


class RandomPolicy(PagedPolicy):
    """Seeded random table order and 0..12 random invoice-level allegations.

    policy_seed is independent of the episode generator's seed. Claims are valid
    JSON findings but deliberately have no reconciliation support.
    """

    def __init__(self, policy_seed=0):
        self.policy_seed = policy_seed

    def reset(self, observation):
        super().reset(observation)
        self.rng = random.Random(self.policy_seed)
        self.rng.shuffle(self.queue)

    def findings(self):
        invoices = sorted(self.tables["invoices"], key=lambda r: r["invoice_id"])
        chosen = self.rng.sample(invoices, self.rng.randint(0, min(12, len(invoices))))
        rows = self.invoice_rows()
        return [self.finding(self.rng.choice(FAMILIES), [invoice["invoice_id"]], invoice["total_minor"],
                             [invoice["doc_id"]] + [r["row_id"] for r in rows[invoice["invoice_id"]]],
                             "Random baseline: unsupported hypothesis.") for invoice in chosen]


class ReconciliationPolicy(PagedPolicy):
    """Simple document-to-ledger aggregate rules, independent of the evaluator.

    Scope: base-currency invoices, one-invoice positive receipts; signed refunds
    are not flagged. Unknown/multi-invoice payment patterns are left unclassified.
    """

    def findings(self):
        result = []
        invoices = {r["invoice_id"]: r for r in self.tables["invoices"]}
        rows = self.invoice_rows()
        start = datetime.fromisoformat(self.manifest["period_start"])
        end = datetime.fromisoformat(self.manifest["period_end"])

        def inside(at):
            return start <= datetime.fromisoformat(at) < end

        for invoice_id, invoice in sorted(invoices.items()):
            sale = rows[invoice_id]
            evidence = [invoice["doc_id"]] + [r["row_id"] for r in sale]
            receivable = sum(r["debit_minor"] - r["credit_minor"] for r in sale if r["account"] == "receivable")
            revenue = sum(r["credit_minor"] - r["debit_minor"] for r in sale if r["account"] == "revenue")
            excess = receivable - invoice["total_minor"]
            if excess > 0 and revenue == receivable:
                result.append(self.finding("duplicate_invoice", [invoice_id], excess, evidence,
                                           "Recognition exceeds the invoice total on both sides."))
            if sale and any(inside(r["timestamp"]) != inside(invoice["issued_at"]) for r in sale):
                result.append(self.finding("period_cutoff", [invoice_id], invoice["total_minor"], evidence,
                                           "Invoice and recognition belong to different reporting periods."))

        by_payment = defaultdict(list)
        for row in self.tables["ledger"]:
            if row["payment_id"] is not None:
                by_payment[row["payment_id"]].append(row)
        base = self.manifest["base_currency"]
        exponents = self.manifest["currency_exponents"]
        for payment in sorted(self.tables["payments"], key=lambda r: r["payment_id"]):
            if payment["amount_minor"] <= 0 or len(payment["invoice_refs"]) != 1 or not inside(payment["timestamp"]):
                continue
            invoice_id = payment["invoice_refs"][0]["invoice_id"]
            if invoice_id not in invoices:
                continue
            linked = by_payment[payment["payment_id"]]
            evidence = [invoices[invoice_id]["doc_id"], payment["doc_id"]] + [r["row_id"] for r in linked]
            expected = payment["amount_minor"]
            if payment["currency"] != base:
                date = datetime.fromisoformat(payment["timestamp"]).astimezone(ZoneInfo(self.manifest["timezone"])).date().isoformat()
                quotes = [r for r in self.tables["fx"] if r["date"] == date
                          and r["source_currency"] == payment["currency"] and r["target_currency"] == base]
                if len(quotes) != 1:
                    continue
                quote = quotes[0]
                expected = convert_minor(payment["amount_minor"], exponents[payment["currency"]],
                                         exponents[base], quote["rate"], self.rules["rounding"])
                evidence.append(f"fx_{date}_{payment['currency']}_{base}")
            booked = sum(r["debit_minor"] - r["credit_minor"] for r in linked if r["account"] == "bank")
            misplaced = sum(r["credit_minor"] - r["debit_minor"] for r in linked if r["account"] == "revenue")
            affected = [invoice_id, payment["payment_id"]]
            if payment["currency"] != base and booked != expected:
                result.append(self.finding("fx_mismatch", affected, abs(booked - expected), evidence,
                                           "Bank value differs from the payment converted at the published daily rate."))
            if misplaced > 0:
                result.append(self.finding("payment_allocation", affected, misplaced, evidence,
                                           "Receipt was credited to revenue instead of the invoice receivable."))
        return result


def make_policy(name, policy_seed=0):
    return {"random": lambda: RandomPolicy(policy_seed), "flag-all": FlagAllPolicy,
            "reconciliation": ReconciliationPolicy}[name]()
