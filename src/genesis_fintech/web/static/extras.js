/* Optional local research tools. All records, scores and runs come from Python. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const el = (tag, text, cls) => { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (cls) n.className = cls; return n; };
  const policies = {reconciliation:"Сверка документов",random:"Случайные гипотезы","flag-all":"Отметить всё"};
  let live = false, current = window.GENESIS_SAMPLES?.interactions, recorded = true, comparison = null;
  let comparisonVersion = 0, starting = false, expired = false;
  let session = null, initial = null, transcript = [], draft = [], cursor = null, closed = true, pending = false, timer = null;
  const status = (message) => { $("extras-status").textContent = message; };
  const settings = () => ({seed:Number($("seed").value),scenario:$("scenario").value});
  async function api(path, payload) {
    const response = await fetch(path, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload),signal:AbortSignal.timeout(15000)});
    if (!response.ok) throw new Error(response.status === 429 ? "Сервер занят. Повторите запрос." : "Запрос отклонён. Проверьте параметры; для ручного аудита при необходимости начните новый эпизод.");
    return response.json();
  }
  function download(content, type, filename) {
    const url = URL.createObjectURL(new Blob([content],{type})); const a = el("a"); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url),1000);
  }
  document.addEventListener("genesis:result", ({detail}) => { current=detail.result; recorded=detail.recorded; });
  $("manual-start").disabled = true;
  if (location.protocol.startsWith("http")) fetch("api/status").then(r => r.json()).then(s => {
    live = s.ok === true && s.mode === "local_demo"; $("manual-start").disabled = !live;
    if (live) status("Сравнение и ручной аудит доступны на локальном сервере.");
  }).catch(() => {});
  status("Файловый preview: сравнение записанных прогонов seed 42. Ручной аудит требует локального сервера.");
  $("compare-button").addEventListener("click", async () => {
    $("compare-button").disabled=true;
    const version = ++comparisonVersion, requested = settings();
    try {
      const result = live ? await api("api/compare",requested) : window.GENESIS_COMPARISONS[requested.scenario];
      if (version !== comparisonVersion) return;
      comparison={...result,source:live?"local_run":"recorded_example"};
      const table=el("table"); const caption=el("caption",`${live?"Новый прогон":"Запись"} · seed ${result.seed} · один эпизод для трёх политик`); table.append(caption);
      const head=el("tr"); ["Политика","TP / FP / FN","F1","Награда","Шаги"].forEach(x => head.append(el("th",x))); const thead=el("thead");thead.append(head);table.append(thead);
      const body=el("tbody"); result.runs.forEach(run => {const row=el("tr");[policies[run.policy],`${run.metrics.tp} / ${run.metrics.fp} / ${run.metrics.fn}`,run.metrics.f1.toFixed(2),run.metrics.reward.toFixed(3),String(run.steps)].forEach(x => row.append(el("td",x)));body.append(row);}); table.append(body);
      $("comparison-result").replaceChildren(table); status(`${live?"Сравнение завершено":"Показано сохранённое сравнение"}. Oracle не используется. Низкая награда не означает сбой протокола.`);
    } catch(error) {if(version === comparisonVersion) status(error.message);} finally {$("compare-button").disabled=false;}
  });
  for(const id of ["scenario","seed"]) $(id).addEventListener(id === "seed" ? "input" : "change",() => {comparisonVersion++;comparison=null;$("comparison-result").replaceChildren();});

  // Edges are explicit record references, never inferred correctness labels.
  document.addEventListener("genesis:evidence", ({detail:{finding,container}}) => {
    document.querySelectorAll(".evidence-graph").forEach(graph => graph.remove());
    const records=finding.evidence.map((x,index) => ({...x,index})).filter(x => x.record); if(!records.length) return;
    const svgNS="http://www.w3.org/2000/svg";
    const node=(tag,attrs,text) => {const n=document.createElementNS(svgNS,tag);Object.entries(attrs).forEach(([k,v]) => n.setAttribute(k,String(v)));if(text!==undefined)n.textContent=text;return n;};
    const lane=(r) => r.row_id?2:r.rate?3:r.payment_id?1:0;
    const labels=["Счета","Платежи","Проводки","Курсы"];
    const counts=[0,0,0,0];
    const positions=records.map((item) => ({...item,x:lane(item.record)*220+15,y:55+counts[lane(item.record)]++*88}));
    const svg=node("svg",{viewBox:`0 0 880 ${Math.max(180,Math.max(...counts)*88+70)}`,role:"group","aria-label":"Связи наблюдённых записей"});
    labels.forEach((text,i) => svg.append(node("text",{x:i*220+15,y:24,class:"graph-lane"},text)));
    const invoices=new Map(positions.filter(x => x.record.doc_id && !x.record.payment_id).map(x => [x.record.invoice_id,x]));
    const payments=new Map(positions.filter(x => x.record.doc_id && x.record.payment_id).map(x => [x.record.payment_id,x]));
    const edges=new Set();
    const connect=(from,to) => {if(!from||from===to||edges.has(`${from.index}:${to.index}`))return;edges.add(`${from.index}:${to.index}`);const a=from.x+180,b=to.x;svg.append(node("path",{d:`M ${a} ${from.y+28} C ${a+35} ${from.y+28}, ${b-35} ${to.y+28}, ${b} ${to.y+28}`,class:"graph-edge"}));};
    positions.forEach(to => {const r=to.record;if(r.row_id){connect(invoices.get(r.invoice_id),to);connect(payments.get(r.payment_id),to);}else if(r.payment_id){(r.invoice_refs||[]).forEach(ref => connect(invoices.get(ref.invoice_id),to));}});
    positions.forEach(item => {
      const group=node("g",{role:"button",tabindex:0,"aria-label":`Открыть запись ${item.id}`,class:"graph-node"});
      group.append(node("rect",{x:item.x,y:item.y,width:180,height:56,rx:3}),node("text",{x:item.x+10,y:item.y+22},`${labels[lane(item.record)]} ${item.index+1}`),node("text",{x:item.x+10,y:item.y+42,class:"graph-id"},item.id.slice(0,10)+"…"+item.id.slice(-6)));
      const open=() => {const details=container.children[item.index];if(details){details.open=true;details.scrollIntoView({block:"nearest"});details.querySelector("summary").focus();}};
      group.addEventListener("click",open);group.addEventListener("keydown",e => {if(e.key==="Enter"||e.key===" "){e.preventDefault();open();}});svg.append(group);
    });
    const graph=el("div",undefined,"evidence-graph"); graph.append(el("p","Связи полученных записей. Линии — явные ссылки; они сами по себе не подтверждают гипотезу."),svg);container.before(graph);
    document.querySelectorAll(".evidence-graph").forEach(other => {if(other!==graph)other.remove();});
  });
  $("report-button").addEventListener("click",() => {
    if(!current)return;
    const doc=document.implementation.createHTMLDocument("Genesis — отчёт аудита");doc.documentElement.lang="ru";
    const css=doc.createElement("style");css.textContent="body{font:400 16px/1.6 \"Helvetica Now Display\",\"Helvetica Neue\",Helvetica,Arial,sans-serif;max-width:900px;margin:40px auto;padding:0 24px;color:#222}h1,h2,h3{font-weight:700;letter-spacing:-.035em;line-height:1.05}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:10px;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f5f2;padding:16px}section{break-inside:avoid}small{color:#666}@media print{body{margin:0}details{display:block}}";doc.head.append(css);
    const add=(tag,text,parent=doc.body) => {const n=doc.createElement(tag);n.textContent=text;parent.append(n);return n;};
    add("h1","Genesis · отчёт аудита");add("p",`${recorded?"Сохранённый пример":"Локальный прогон"} · ${current.scenario} · seed ${current.seed} · ${policies[current.policy]}`);
    add("p",`F1 ${current.metrics.f1.toFixed(2)} · TP ${current.metrics.tp} · FP ${current.metrics.fp} · FN ${current.metrics.fn} · награда ${current.metrics.reward.toFixed(3)} · шаги ${current.steps}`);
    add("small","Синтетические данные. Это демонстрация алгоритма, а не профессиональное аудиторское заключение. HTML можно распечатать или сохранить в PDF средствами браузера.");
    add("h2","Находки и полученные доказательства");if(!current.findings.length)add("p",`Находки отсутствуют; пропущено ${current.metrics.fn}.`);
    current.findings.forEach((finding,index) => {const section=doc.createElement("section");doc.body.append(section);add("h2",`${index+1}. ${finding.type}`,section);add("p",`Заявлено ${finding.claimed_amount_minor} минимальных единиц ${finding.currency}. ${finding.explanation}`,section);finding.evidence.forEach(item => {add("h3",item.id,section);add("pre",item.record?JSON.stringify(item.record,null,2):"Запись не была получена политикой",section);});});
    if(comparison){add("h2","Сравнение политик");add("p",`Источник: ${comparison.source}; seed ${comparison.seed}; сценарий ${comparison.scenario}.`);add("pre",JSON.stringify(comparison.runs,null,2));}
    add("h2","Траектория");add("pre",JSON.stringify(current.timeline,null,2));download("<!doctype html>\n"+doc.documentElement.outerHTML,"text/html;charset=utf-8",`genesis-report-${current.scenario}-${current.seed}.html`);
  });

  const splitIds=(text) => text.split(",").map(x => x.trim()).filter(Boolean);
  function controls(){$("manual-start").disabled=!live||pending||starting||(!closed&&!expired);$("manual-start").textContent=(closed||expired)?"Начать ручной эпизод ↗":"Ручной эпизод идёт";document.querySelectorAll("#manual-workspace button,#manual-workspace input,#manual-workspace select").forEach(x => {x.disabled=starting||pending||closed;});$("manual-next").disabled=starting||pending||closed||!cursor;$("manual-export").disabled=starting||pending||!closed;}
  function budget(seconds,steps){clearInterval(timer);const end=Date.now()+seconds*1000;const update=() => {const left=Math.max(0,Math.ceil((end-Date.now())/1000));$("manual-budget").textContent=`Шаги: ${steps} / 100 · осталось ${left} с${left===0&&!closed?" · время вышло, завершите эпизод":""}`;if(left===0&&!closed){expired=true;controls();}if(left===0||closed)clearInterval(timer);};update();if(!closed)timer=setInterval(update,1000);}
  async function action(request){if(pending||closed||starting)return;pending=true;controls();try{const result=await api("api/manual/step",{session,action:request});transcript.push({action:request,...result});closed=result.terminated||result.truncated;budget(result.remaining_seconds,result.steps);if(closed){$("manual-score").hidden=false;$("manual-score").textContent=JSON.stringify({terminated:result.terminated,truncated:result.truncated,...result.metrics},null,2);$("manual-export").hidden=false;status(result.truncated?"Ручной эпизод прерван по бюджету; оценён пустой ответ.":"Ручной аудит завершён. Итоговая оценка открыта.");}return result;}catch(error){status(error.message);}finally{pending=false;controls();}}
  function renderDraft() {
    $("manual-draft").textContent = `Находок в ответе: ${draft.length}`;
    const rows = draft.map((finding, index) => {
      const row = el("li");
      row.append(el("span", `${index+1}. ${finding.type} · ${finding.claimed_amount_minor} ${finding.currency}`));
      const remove = el("button", "Удалить", "text-button"); remove.type = "button";
      remove.setAttribute("aria-label", `Удалить находку ${index+1}`);
      remove.addEventListener("click", () => {if(pending||closed)return;draft.splice(index,1);renderDraft();controls();});
      row.append(remove); return row;
    });
    $("manual-draft-list").replaceChildren(...rows);
  }
  $("manual-start").addEventListener("click",async () => {
    if(starting||pending||(!closed&&!expired)||!live)return;
    starting=true;controls();const requested=settings();
    try {
      const result=await api("api/manual/start",requested);
      session=result.session;initial=result.observation;draft=[];transcript=[];cursor=null;closed=false;expired=false;
      $("finding-builder").reset();$("manual-record-id").value="";$("manual-expression").value="";$("manual-value").textContent="";
      $("manual-workspace").hidden=false;$("manual-records").replaceChildren();$("manual-score").hidden=true;$("manual-export").hidden=true;
      $("manual-currency").value=initial.manifest.base_currency;
      $("manual-episode").textContent=`Сценарий: ${requested.scenario} · seed ${requested.seed} · ${initial.manifest.episode_id}. Параметры этого эпизода зафиксированы до завершения.`;
      renderDraft();budget(result.remaining_seconds,0);status("Эпизод начат. Запрашивайте документы и собирайте доказательства.");
    } catch(error) {status(error.message);} finally {starting=false;controls();}
  });
  async function list(next){const result=await action({action:"list_records",params:{table:$("manual-table").value,cursor:next?cursor:null,limit:20}});if(!result)return;const page=result.observation.result;cursor=page?.next_cursor||null;$("manual-records").replaceChildren();if(page?.records)page.records.forEach(record => {const id=record.row_id||record.doc_id||`fx_${record.date}_${record.source_currency}_${record.target_currency}`;const details=el("details"), summary=el("summary",id);details.append(summary,el("pre",JSON.stringify(record,null,2)));const use=el("button","Взять ID доказательства","text-button");use.type="button";use.addEventListener("click",() => {const ids=splitIds($("manual-evidence").value);if(!ids.includes(id))ids.push(id);$("manual-evidence").value=ids.join(", ");});details.append(use);$("manual-records").append(details);});else status(result.observation.error||"Эпизод завершён.");controls();}
  $("manual-list").addEventListener("click",() => list(false));$("manual-next").addEventListener("click",() => list(true));$("manual-table").addEventListener("change",() => {cursor=null;controls();});
  async function fetchRecord(documentOnly){const id=$("manual-record-id").value.trim();if(!id)return;const result=await action(documentOnly?{action:"get_document",params:{doc_id:id}}:{action:"get_record",params:{table:$("manual-table").value,id}});if(result){$("manual-records").replaceChildren(el("pre",JSON.stringify(result.observation,null,2)));cursor=null;controls();}}
  $("manual-fetch").addEventListener("click",() => fetchRecord(false));$("manual-document").addEventListener("click",() => fetchRecord(true));
  $("manual-calculate").addEventListener("click",async () => {const result=await action({action:"calculator",params:{expression:$("manual-expression").value}});if(result)$("manual-value").textContent=result.observation.result?.value??result.observation.error??"Эпизод завершён";});
  $("finding-builder").addEventListener("submit",event => {event.preventDefault();const amount=Number($("manual-amount").value);if(closed||pending)return;if(draft.length>=30||!Number.isSafeInteger(amount)||amount<0){status("До 30 находок; сумма должна быть целым неотрицательным числом.");return;}draft.push({type:$("manual-type").value,affected_ids:splitIds($("manual-affected").value),claimed_amount_minor:amount,currency:$("manual-currency").value.toUpperCase(),evidence_ids:splitIds($("manual-evidence").value),explanation:$("manual-explanation").value});renderDraft();controls();});
  $("manual-clear").addEventListener("click",() => {if(pending||closed)return;draft=[];renderDraft();controls();});
  $("manual-submit").addEventListener("click",() => action({action:"submit",params:{episode_id:initial.manifest.episode_id,findings:draft}}));
  $("manual-export").addEventListener("click",() => download(JSON.stringify({source:"local_manual",initial,transcript},null,2),"application/json",`genesis-manual-${initial.manifest.episode_id}.json`));
})();
