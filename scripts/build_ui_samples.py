"""Rebuild explicitly labelled UI recordings from the actual engine, without truth.

Run from the repository root: PYTHONPATH=src python scripts/build_ui_samples.py
"""

import json
from pathlib import Path

from genesis_fintech.web.app import run_view


if __name__ == "__main__":
    destination = Path(__file__).resolve().parents[1] / "src/genesis_fintech/web/static/samples.js"
    samples = {name: run_view({"seed": 42, "scenario": name, "policy": "reconciliation"})
               for name in ("interactions", "independent", "clean")}
    destination.write_text(
        "/* Recorded real engine runs: seed 42, reconciliation. Rebuild with scripts/build_ui_samples.py. */\n"
        + "window.GENESIS_SAMPLES = " + json.dumps(samples, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )
    print(f"Recorded {len(samples)} actual engine runs: {destination}")
