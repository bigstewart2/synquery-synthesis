// Exercise workspace migration and persistence without browser or paid model calls.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const script = fs.readFileSync(require('node:path').join(__dirname,'../public/index.html'),'utf8').split('<script>')[1].split('</script>')[0];
function workspace(seed={}, failWrite=()=>false) {
  const data = new Map(Object.entries(seed)), nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id,{value:'',textContent:'',innerHTML:'',disabled:false,
      classList:{values:new Set(), toggle(name,on){if(on)this.values.add(name);else this.values.delete(name)},contains(name){return this.values.has(name)}}, style:{}, addEventListener(){}, querySelectorAll(){return []}, click(){}});
    return nodes.get(id);
  };
  const context = vm.createContext({
    structuredClone, console, crypto:require('node:crypto').webcrypto, setTimeout,clearTimeout,
    document:{querySelector:node,querySelectorAll:()=>[]},
    window:{addEventListener(){}},location:{reload(){}}, navigator:{},
    localStorage:{getItem:k=>data.get(k)??null,setItem:(k,v)=>{if(failWrite(k,v))throw new Error("quota");data.set(k,v)}},
    sessionStorage:{getItem:()=>null,setItem(){}},
  });
  vm.runInContext(script,context);
  return {data,nodes,context,run:s=>vm.runInContext(s,context)};
}
let w=workspace();
assert.equal(w.run('state.mode'),'brief');
assert.equal(w.run('state.briefReady'),false);
w.run('state.briefDraft.project="Research draft"; save()');
w=workspace(Object.fromEntries(w.data));
assert.equal(w.run('state.briefDraft.project'),'Research draft');

const old={experts:{E1:{atoms:{pricing:[]},stats:{total:0,verified:0,elapsed_s:0,usage:{input_tokens:0,output_tokens:0}},labels:{},failures:[]}},order:['E1'],marks:{'E1:pricing:0':'y'},themes:'Keep these notes'};
w=workspace({'synq.live.v2':JSON.stringify(old)});
assert.equal(w.run('state.mode'),'brief');
assert.equal(w.run('state.briefReady'),false);
assert.equal(w.run('state.order.length'),0);
const archived=JSON.parse(w.data.get('synq.live.v3.projects'));
const id=Object.keys(archived)[0];
assert.equal(archived[id].themes,old.themes);
assert.equal(archived[id].marks['E1:pricing:0'],'y');
assert.equal(w.data.get('synq.live.v2'),JSON.stringify(old));
assert.equal(w.nodes.get('#storageNotice').textContent,'');

w=workspace();
w.run('save(); state.briefDraft.project="Unsaved work"; localStorage.setItem=()=>{throw new Error("quota")}; archiveCurrent()');
assert.equal(w.run('state.briefDraft.project'),'Unsaved work');

w=workspace();w.run('save()');
w.data.set('synq.live.v3','{"another":"tab"}');
assert.equal(w.run('save()'),false);
assert.equal(w.run('externalChange'),true);
assert.equal(w.data.get('synq.live.v3'),'{"another":"tab"}');

w=workspace();w.run('state.briefId="a"');
assert.equal(w.run('eligible({verified:true,review_status:"supported",brief_id:"a"})'),true);
for (const expression of [
 'eligible({verified:false,review_status:"supported",brief_id:"a"})',
 'eligible({verified:true,review_status:"flagged",brief_id:"a"})',
 'eligible({verified:true,review_status:"supported",brief_id:"b"})']) assert.equal(w.run(expression),false);
w.run('state.draft={summary:"stale"};state.checks=[{claim:"stale"}];invalidateOutput()');
assert.equal(w.run('state.draft'),null);assert.equal(w.run('state.checks.length'),0);
console.log('PASS: draft restoration, legacy migration, archive preservation, quota recovery, cross-tab guard, evidence eligibility and output invalidation.');

// The first visit requires an explicit choice. Displayed fields never set the brief.
w=workspace();
w.run('$("#briefForm").onsubmit({preventDefault(){}})');
assert.equal(w.run('state.briefReady'),false);
w.run('$("#harborExample").onclick(); $("#briefProject").value="Injected custom project"; $("#briefForm").onsubmit({preventDefault(){}})');
assert.equal(w.run('state.briefReady'),true);
assert.equal(w.run('researchPayload().brief.project'),'Harbor payments diligence');
assert.equal(w.run('researchPayload().brief.questions.length'),5);
w=workspace(Object.fromEntries(w.data));
assert.equal(w.run('state.briefReady'),true,'Refresh restores explicit selection');

// Exactly two samples, stable expert labels, no duplicate queued or loaded inputs.
w.run('addSample("custom"); addSample("harbor-maria"); addSample("harbor-maria"); $("#addBoth").onclick()');
assert.equal(w.run('state.queue.length'),2);
assert.equal(w.run('state.queue[0].label'),'E2','Maria keeps her identity even when selected first');
w.run('state.queue=[]; state.experts.E2={}; addSample("harbor-maria")');
assert.equal(w.run('state.queue.length'),0,'Loaded interviews cannot be added again');
w.run('busy=true;addSample("harbor-david")');assert.equal(w.run('state.queue.length'),0);
w.run('busy=false;state.demoId=null;addSample("harbor-david")');assert.equal(w.run('state.queue.length'),0);

// A v3 general workspace is historical, never silently relabeled as a guided run.
w=workspace({'synq.live.v3':JSON.stringify({...old, projectId:'prior', mode:'brief',briefReady:true,brief:{project:'Custom',decision:'Keep',questions:['Why?']},briefDraft:{project:'Custom'}})});
assert.equal(w.run('isHarbor()'),true);
assert.equal(JSON.parse(w.data.get('synq.live.v3.projects')).prior.brief.project,'Custom');
assert.equal(w.run('state.briefReady'),false);
console.log('PASS: explicit sample choice, immutable canonical brief, stable sample identities, duplicate prevention and preserved historical workspaces.');

(async () => {
  const flow=workspace();
  flow.run(`
    let requests=[], failMaria=true;
    fetch=async (url, options)=>{
      const payload=JSON.parse(options.body);requests.push(payload);
      if(payload.sample_id==='harbor-maria' && failMaria) return {ok:false,status:503,json:async()=>({ok:false,error:'Try again'})};
      const sample=HARBOR.samples.find(s=>s.id===payload.sample_id);
      return {ok:true,status:200,json:async()=>({ok:true,expert:sample.label,filename:sample.filename,brief_id:'harbor',atoms:{findings:[]},labels:{findings:'Findings'},stats:{total:0,verified:0,elapsed_s:0,usage:{input_tokens:0,output_tokens:0}},failures:[]})};
    };
    $('#harborExample').onclick();$('#briefForm').onsubmit({preventDefault(){}});$('#addBoth').onclick();
  `);
  assert.equal(flow.run('requests.length'),0,'Selecting a brief and samples must not call the model');
  await flow.run('$("#run").onclick()');
  assert.equal(flow.run('state.order.join(",")'),'E1');
  assert.equal(flow.run('state.queue.find(q=>q.label==="E2").status'),'failed');
  assert.equal(flow.run('busy'),false,'Failure must unlock the workspace');
  flow.run('failMaria=false');
  await flow.run('$("#run").onclick()');
  assert.equal(flow.run('state.order.join(",")'),'E1,E2');
  assert.equal(flow.run('requests.filter(r=>r.sample_id==="harbor-david").length'),1,'Retry must not charge for a completed interview again');
  assert.equal(flow.run('requests.every(r=>!r.b64&&!r.filename&&!r.expert)'),true);
  const restored=workspace(Object.fromEntries(flow.data));
  assert.equal(restored.run('state.order.length'),2,'Completed guided results survive refresh');
  console.log('PASS: no automatic calls, partial failure recovery, sample-only request bodies and retry without repeating successful extraction.');
})().catch(error=>{ console.error(error);process.exitCode=1; });

// Regression: an old saved Harbor brief with no interviews must not open a dead panel.
const stranded={projectId:'old-brief',mode:'brief',briefReady:true,
 brief:{project:'Harbor payments diligence',decision:'Saved decision',questions:['Why?']},
 briefDraft:{project:'Harbor payments diligence',decision:'Saved decision',questionsText:'Why?'},
 order:[],experts:{},marks:{},themes:'Keep these notes'};
const entry=workspace({'synq.live.v3':JSON.stringify(stranded)});
assert.equal(entry.run('isHarbor()'),true,'An older active workspace should be archived before opening the guided demo');
assert.equal(entry.run('state.briefReady'),false,'The visitor must choose Use the Harbor example');
assert.equal(JSON.parse(entry.data.get('synq.live.v3.projects'))['old-brief'].themes,'Keep these notes');

const refreshed=workspace(Object.fromEntries(entry.data));
assert.equal(Object.keys(JSON.parse(refreshed.data.get('synq.live.v3.projects'))).length,1,'Refresh must not create duplicate archives');
entry.run('renderAll()');
assert.equal(entry.nodes.get('#analysisWorkspace').classList.contains('hide'),true);
assert.equal(entry.nodes.get('#briefIntake').classList.contains('hide'),false);
entry.run('state={...freshProject(),...projects()["old-brief"],demoId:null};save();renderAll()');
assert.equal(entry.run('isHarbor()'),false);
assert.equal(entry.nodes.get('#earlierDraft').classList.contains('hide'),false,'Opening an empty historical run must explain its state');
assert.equal(entry.nodes.get('#analysisWorkspace').classList.contains('hide'),true,'Do not show a dead Add interview control');
assert.equal(entry.nodes.get('#earlierDraftNotes').textContent,'Keep these notes');
entry.run('$("#startFromDraft").onclick()');
assert.equal(entry.run('isHarbor()'),true);
assert.equal(entry.run('state.briefReady'),false);

const blockedArchive=workspace({'synq.live.v3':JSON.stringify(stranded)},key=>key.endsWith('.projects'));
assert.equal(blockedArchive.run('state.projectId'),'old-brief','An archive failure must keep the earlier active workspace');
assert.equal(JSON.parse(blockedArchive.data.get('synq.live.v3')).themes,'Keep these notes');
assert.match(blockedArchive.nodes.get('#storageNotice').textContent,/could not save/);
const blockedSwitch=workspace({'synq.live.v3':JSON.stringify(stranded)},(key,value)=>key==='synq.live.v3' && JSON.parse(value).demoId==='harbor-v1');
assert.equal(blockedSwitch.run('state.projectId'),'old-brief','An active-record failure must not hide the older workspace');
assert.equal(JSON.parse(blockedSwitch.data.get('synq.live.v3.projects'))['old-brief'].themes,'Keep these notes');
console.log('PASS: old empty brief opens guided intake, archives persist without duplication, historical drafts have a way out and archive-write failure recovery.');

// Coverage counts only eligible, confirmed findings and keeps names tied to labels.
const coverage=workspace();
coverage.run(`
  state.brief=structuredClone(HARBOR.brief);state.briefId='harbor';state.order=['E2','E1'];
  const supported={question_index:0,verified:true,review_status:'supported',brief_id:'harbor'};
  state.experts={E2:{atoms:{findings:[supported,supported,{...supported,review_status:'flagged'}]}},E1:{atoms:{findings:[supported]}}};
  state.marks={'E2:findings:0':'y','E2:findings:2':'y','E1:findings:0':'n'};
`);
const coverageHtml=coverage.run('buildCoverage()');
assert.match(coverageHtml,/Maria Castellanos · Sales \(E2\)/);
assert.match(coverageHtml,/David Okafor · Operations \(E1\)/);
assert.match(coverageHtml,/<td class="num">1<\/td><td class="num">0<\/td>/,'Unconfirmed, rejected and flagged findings must not contribute to counts');
assert.match(coverageHtml,/counts, not quality or confidence scores/);
console.log('PASS: coverage names follow interview identity and counts include only eligible confirmed findings.');
