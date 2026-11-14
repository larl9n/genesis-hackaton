/* Event-level regression checks without a browser or external dependencies. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor() { this.handlers = {}; this.children = []; this.value = ''; this.disabled = false; }
  addEventListener(type, fn) { this.handlers[type] = fn; }
  fire(type) { return this.handlers[type]?.({preventDefault() {}}); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  setAttribute() {}
  reset() {}
}
const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r; }); return {promise, resolve}; };
async function check() {
  const elements = new Map();
  const get = id => { if (!elements.has(id)) elements.set(id, new Element()); return elements.get(id); };
  const requests = []; let clock = 0, tick;
  const document = {getElementById:get, createElement:() => new Element(), addEventListener() {}, querySelectorAll:() => []};
  const context = {document, window:{}, location:{protocol:'http:'}, AbortSignal:{timeout() {}},
    Date:{now:() => clock}, setInterval:fn => {tick=fn;return 1;}, clearInterval() {},
    fetch:(url, options) => {
      if(url === 'api/status')return Promise.resolve({json:async () => ({ok:true,mode:'local_demo'})});
      const pending=deferred(); requests.push({url,body:JSON.parse(options.body),pending});
      return pending.promise.then(result => ({ok:true,json:async () => result}));
    }};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../src/genesis_fintech/web/static/extras.js'),'utf8'),context);
  await new Promise(resolve => setImmediate(resolve));
  get('seed').value='42';get('scenario').value='interactions';
  const compare=get('compare-button').fire('click');
  get('scenario').value='clean';get('scenario').fire('change');
  requests.at(-1).pending.resolve({seed:42,runs:[]});await compare;
  assert.equal(get('comparison-result').children.length,0,'late comparison must not replace changed settings');

  const start=get('manual-start').fire('click');
  await get('manual-start').fire('click');
  assert.equal(requests.filter(r => r.url==='api/manual/start').length,1,'double start is ignored');
  requests.at(-1).pending.resolve({session:'session1',remaining_seconds:60,observation:{manifest:{episode_id:'episode1',base_currency:'KZT'}}});await start;
  assert.equal(get('manual-start').disabled,true,'running episode cannot be replaced');
  for(const [id,value] of Object.entries({'manual-amount':'100','manual-type':'duplicate_invoice','manual-affected':'row_a','manual-evidence':'doc_b','manual-explanation':'Evidence'}))get(id).value=value;
  get('finding-builder').fire('submit');get('manual-amount').value='200';get('finding-builder').fire('submit');
  assert.equal(get('manual-draft-list').children.length,2);
  get('manual-draft-list').children[0].children[1].fire('click');
  assert.equal(get('manual-draft-list').children.length,1,'single finding removed');
  const submit=get('manual-submit').fire('click');
  const sent=requests.at(-1);
  assert.equal(sent.body.action.params.findings.length,1);
  assert.equal(sent.body.action.params.findings[0].claimed_amount_minor,200,'remaining finding is submitted');
  assert.equal(get('manual-start').disabled,true,'start locked during outstanding action');
  sent.pending.resolve({terminated:true,truncated:false,remaining_seconds:50,steps:1,metrics:{f1:0},observation:{}});await submit;
  assert.equal(get('manual-start').disabled,false);
  const second=get('manual-start').fire('click');
  requests.at(-1).pending.resolve({session:'session2',remaining_seconds:60,observation:{manifest:{episode_id:'episode2',base_currency:'KZT'}}});await second;
  assert.equal(get('manual-draft-list').children.length,0,'new episode clears old draft');
  clock=61000;tick();
  assert.equal(get('manual-start').disabled,false,'expired episode can be restarted');
  console.log('UI interactions: stale comparison, session lifecycle, draft removal, timeout recovery passed');
}
check().catch(error => { console.error(error); process.exitCode=1; });
