/* Local UI; all audit results come from the Python engine or labelled recordings. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const names = {duplicate_invoice: "Дублирование счёта", payment_allocation: "Распределение платежа", fx_mismatch: "Валютное расхождение", period_cutoff: "Граница отчётного периода"};
  const explanations = {
    duplicate_invoice: "Признанная в проводках сумма превышает сумму подтверждённого счёта.",
    payment_allocation: "Часть поступления отнесена на выручку вместо погашения задолженности по счёту.",
    fx_mismatch: "Сумма банковской проводки отличается от платежа, пересчитанного по опубликованному курсу.",
    period_cutoff: "Счёт и его признание в книге попали в разные отчётные периоды."
  };
  const tableNames = {ledger: "Проводки", invoices: "Счета", payments: "Платежи", fx: "Курсы валют"};
  let live = false;
  let current = null;
  let currentRecorded = true;
  let opener = null;
  const element = (tag, className, text) => { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; };
  const shortId = (id) => id.length > 24 ? `${id.slice(0, 9)}…${id.slice(-8)}` : id;
  const plural = (count, words) => words[count % 100 >= 11 && count % 100 <= 14 ? 2 : count % 10 === 1 ? 0 : count % 10 >= 2 && count % 10 <= 4 ? 1 : 2];
  const money = (amount, currency) => {
    const exponent = current?.manifest?.currency_exponents?.[currency] ?? 2;
    return new Intl.NumberFormat("ru-RU", {minimumFractionDigits: exponent, maximumFractionDigits: exponent}).format(amount / 10 ** exponent) + " " + currency;
  };

  function openDialog(dialog, trigger) {
    opener = trigger || document.activeElement;
    dialog.showModal();
    document.body.classList.add("dialog-open");
    dialog.querySelector(".close-button").focus();
  }
  function closeDialog(dialog) { dialog.close(); }
  for (const id of ["evidence-dialog", "about-dialog"]) {
    const dialog = $(id);
    dialog.addEventListener("close", () => { document.body.classList.remove("dialog-open"); if (opener?.isConnected) opener.focus(); });
    dialog.addEventListener("click", (event) => { if (event.target === dialog) { const rect = dialog.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) closeDialog(dialog); } });
  }
  $("close-evidence").addEventListener("click", () => closeDialog($("evidence-dialog")));
  $("close-about").addEventListener("click", () => closeDialog($("about-dialog")));
  $("about-button").addEventListener("click", (event) => openDialog($("about-dialog"), event.currentTarget));

  function showEvidence(index, trigger) {
    const finding = current?.findings[index];
    if (!finding) return;
    $("evidence-title").textContent = names[finding.type] || finding.type;
    const explanation = current.metrics.fp === 0 ? explanations[finding.type] : "Гипотеза политики. Откройте записи и проверьте, подтверждается ли обвинение: этот прогон содержит ложные находки.";
    $("evidence-summary").textContent = `${explanation} Заявленная сумма: ${money(finding.claimed_amount_minor, finding.currency)}.`;
    const container = $("evidence-records"); container.replaceChildren();
    finding.evidence.forEach((evidence, position) => {
      const details = element("details"); if (position === 0) details.open = true;
      const summary = element("summary", "", `${String(position + 1).padStart(2, "0")} / ${evidence.id}`);
      const content = element("pre", "", evidence.record ? JSON.stringify(evidence.record, null, 2) : "Эта запись не была получена политикой через инструменты.");
      details.append(summary, content); container.append(details);
    });
    openDialog($("evidence-dialog"), trigger);
  }

  function proofBoard() {
    const finding = current.findings[0];
    const board = $("proof-records"); board.replaceChildren();
    $("proof-open").hidden = !finding;
    if (!finding) {
      $("proof-type").textContent = current.metrics.fn || current.truncated ? "Находки не отправлены" : "Чистая компания";
      $("proof-amount").textContent = current.truncated ? "Эпизод прерван." : current.metrics.fn ? "Есть ненайденные ошибки." : "Без ложных обвинений.";
      const note = element("div", "proof-record"); note.append(element("p", "", "РЕЗУЛЬТАТ СВЕРКИ"), element("div", "", `Найдено ${current.metrics.tp} ошибок. Ложных тревог: ${current.metrics.fp}.`)); board.append(note); return;
    }
    $("proof-type").textContent = (current.metrics.fp ? "Гипотеза · " : "") + (names[finding.type] || finding.type);
    $("proof-amount").textContent = money(finding.claimed_amount_minor, finding.currency);
    finding.evidence.filter((item) => item.record).slice(0, 2).forEach((item) => {
      const record = item.record;
      const kind = record.row_id ? "ПРОВОДКА" : record.payment_id ? "ДОКУМЕНТ / ПЛАТЁЖ" : record.rate ? "КОТИРОВКА" : "ДОКУМЕНТ / СЧЁТ";
      const panel = element("div", "proof-record"); panel.append(element("p", "", kind));
      const dl = element("dl");
      const pairs = [["ID", shortId(item.id)]];
      if (record.total_minor !== undefined) pairs.push(["Сумма", money(record.total_minor, record.currency)]);
      if (record.debit_minor !== undefined) { pairs.push(["Дебет", money(record.debit_minor, record.currency)]); pairs.push(["Кредит", money(record.credit_minor, record.currency)]); }
      if (record.amount_minor !== undefined) pairs.push(["Сумма", money(record.amount_minor, record.currency)]);
      if (record.account) pairs.push(["Счёт учёта", record.account]);
      if (record.rate) pairs.push(["Курс", record.rate]);
      if (record.issued_at || record.timestamp || record.date) pairs.push(["Дата", (record.issued_at || record.timestamp || record.date).slice(0, 10)]);
      pairs.forEach(([label, value]) => dl.append(element("dt", "", label), element("dd", "", value)));
      panel.append(dl); board.append(panel);
    });
  }

  function render(result, recorded) {
    current = result;
    currentRecorded = recorded;
    $("metric-f1").textContent = result.metrics.f1.toFixed(2);
    $("metric-found").textContent = `${result.metrics.tp} / ${result.metrics.fn}`;
    $("metric-fp").textContent = String(result.metrics.fp);
    $("metric-steps").replaceChildren(document.createTextNode(String(result.steps) + " "), element("small", "", "/ 100"));
    $("metric-reward").textContent = result.metrics.reward.toFixed(3);
    $("records-caption").textContent = `${result.manifest.document_count} ${plural(result.manifest.document_count, ["документ", "документа", "документов"])} · ${result.manifest.row_count} ${plural(result.manifest.row_count, ["проводка", "проводки", "проводок"])}`;
    $("episode-caption").textContent = `SEED ${result.seed} / ${recorded ? "ЗАПИСЬ" : "НОВЫЙ ПРОГОН"}`;
    $("result-label").textContent = result.truncated ? "Эпизод прерван" : result.metrics.fp ? "Прогон завершён · есть ложные тревоги" : result.metrics.fn ? "Прогон завершён · есть пропуски" : recorded ? "Пример завершён" : "Аудит завершён";
    $("result-label").parentElement.classList.toggle("is-failure", !!(result.truncated || result.metrics.fp || result.metrics.fn));
    $("finding-count").textContent = String(result.findings.length);
    $("step-count").textContent = String(result.timeline.length);
    const list = $("findings-list"); list.replaceChildren();
    if (!result.findings.length) {
      const empty = element("div", "empty-state"); empty.append(element("span", "", result.truncated || result.metrics.fn ? "—" : "✓"), document.createTextNode(result.truncated ? "Эпизод прерван. Пустой ответ не означает отсутствие ошибок." : result.metrics.fn ? "Политика воздержалась. В этом эпизоде остались ненайденные ошибки." : "Расхождений не обнаружено. Чистые данные не требуют обвинений.")); list.append(empty);
    }
    result.findings.forEach((finding, index) => {
      const row = element("button", "finding-row"); row.type = "button";
      row.setAttribute("aria-label", `Открыть доказательства: ${names[finding.type] || finding.type}, ${money(finding.claimed_amount_minor, finding.currency)}`);
      const left = element("span", "finding-left"); left.append(element("span", "finding-index", String(index + 1).padStart(2, "0")));
      const title = element("span"); title.append(element("span", "finding-name", names[finding.type] || finding.type), element("span", "finding-id", shortId(finding.affected_ids[0]))); left.append(title);
      const right = element("span", "finding-right"); const amount = element("span"); amount.append(element("span", "finding-amount", money(finding.claimed_amount_minor, finding.currency)), element("span", "finding-evidence", `${finding.evidence.length} ДОКАЗАТЕЛЬСТВ`)); right.append(amount, element("span", "finding-arrow", "↗")); row.append(left, right);
      row.addEventListener("click", () => showEvidence(index, row)); list.append(row);
    });
    const trajectory = $("trajectory-list"); trajectory.replaceChildren();
    result.timeline.forEach((step) => {
      const line = element("li");
      const action = step.action === "submit" ? "Отправка находок" : step.action === "list_records" ? (tableNames[step.table] || step.table) : step.action || "Завершение";
      line.append(element("span", "", String(step.step).padStart(2, "0")), element("span", "", action), element("span", "", step.error ? "Ошибка запроса" : step.action === "submit" ? `${result.findings.length} находок ↗` : `${step.records} записей`)); trajectory.append(line);
    });
    proofBoard();
    $("result-announcement").textContent = `Прогон завершён. Найдено: ${result.metrics.tp}, пропущено: ${result.metrics.fn}, ложных тревог: ${result.metrics.fp}.`;
  }

  function selectTab(tab) {
    for (const name of ["findings", "trajectory"]) {
      const selected = tab.id === `tab-${name}`;
      $(`tab-${name}`).setAttribute("aria-selected", String(selected));
      $(`tab-${name}`).tabIndex = selected ? 0 : -1;
      $(`panel-${name}`).hidden = !selected;
    }
  }
  const tabs = [$("tab-findings"), $("tab-trajectory")];
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectTab(tab));
    tab.addEventListener("keydown", (event) => {
      if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) {
        event.preventDefault(); const next = event.key === "Home" ? tabs[0] : event.key === "End" ? tabs[1] : tabs[1 - index]; selectTab(next); next.focus();
      }
    });
  });
  $("proof-open").addEventListener("click", (event) => showEvidence(0, event.currentTarget));
  $("export-button").addEventListener("click", () => {
    if (!current) return;
    const blob = new Blob([JSON.stringify({source: currentRecorded ? "recorded_example" : "local_run", ...current}, null, 2)], {type:"application/json"});
    const url = URL.createObjectURL(blob); const link = element("a"); link.href = url; link.download = `genesis-${current.scenario}-${current.seed}.json`; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  function recordedMode() {
    live = false; $("seed").readOnly = true; $("seed").value = "42"; $("policy").value = "reconciliation"; $("policy").disabled = true;
    $("connection-label").textContent = "ПРЕДПРОСМОТР / ЗАПИСЬ";
    $("mode-description").textContent = "Записанные прогоны seed 42. Для новых параметров: python -m genesis_fintech serve.";
    $("run-button-text").textContent = "Смотреть пример";
  }
  $("run-form").addEventListener("submit", async (event) => {
    event.preventDefault(); $("run-error").hidden = true;
    const scenario = $("scenario").value;
    if (!live) { render(window.GENESIS_SAMPLES[scenario], true); selectTab($("tab-findings")); return; }
    const seed = Number($("seed").value);
    if (!Number.isInteger(seed) || seed < 0 || seed > 2147483647) { $("run-error").textContent = "Введите целый seed от 0 до 2147483647."; $("run-error").hidden = false; return; }
    $("run-button").disabled = true; $("results").setAttribute("aria-busy", "true"); $("run-form").classList.add("is-running"); $("run-button-text").textContent = "Идёт сверка";
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch("api/run", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({seed,scenario,policy:$("policy").value}), signal:controller.signal});
      if (!response.ok) throw new Error(response.status === 429 ? "Сейчас выполняется другой прогон. Повторите через несколько секунд." : "Не удалось выполнить прогон. Проверьте локальный сервер и параметры.");
      render(await response.json(), false); selectTab($("tab-findings"));
    } catch (error) {
      $("run-error").textContent = error.name === "AbortError" ? "Сервер не ответил вовремя. Предыдущий результат сохранён." : error.message || "Сервер недоступен. Предыдущий результат сохранён."; $("run-error").hidden = false;
    } finally { clearTimeout(timeout); $("run-button").disabled = false; $("results").setAttribute("aria-busy", "false"); $("run-form").classList.remove("is-running"); $("run-button-text").textContent = "Запустить аудит"; }
  });
  recordedMode();
  for (const id of ["scenario", "policy", "seed"]) {
    $(id).addEventListener("change", () => {
      if (!live) render(window.GENESIS_SAMPLES[$("scenario").value], true);
      else if (current) $("result-label").textContent = "Результат предыдущего прогона";
    });
  }
  if (window.GENESIS_SAMPLES?.interactions) render(window.GENESIS_SAMPLES.interactions, true);
  if (location.protocol === "http:" || location.protocol === "https:") {
    fetch("api/status").then((response) => response.ok ? response.json() : Promise.reject()).then((status) => {
      if (!status.ok || status.mode !== "local_demo") return;
      live = true; $("seed").readOnly = false; $("policy").disabled = false; $("connection-label").textContent = "ЛОКАЛЬНЫЙ СЕРВЕР / ГОТОВ";
      $("mode-description").textContent = "Выберите параметры и выполните новый прогон алгоритма сверки. Обучение модели не запускается.";
      $("run-button-text").textContent = "Запустить аудит";
    }).catch(() => { /* A static preview remains a clearly labelled recording. */ });
  }
})();
