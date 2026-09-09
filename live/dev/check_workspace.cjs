// Exercise workspace migration and persistence without browser or paid model calls.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const script = fs.readFileSync(require('node:path').join(__dirname,'../public/index.html'),'utf8').split('<script>')[1].split('</script>')[0];
function workspace(seed={}) {
  const data = new Map(Object.entries(seed)), nodes = new Map();
  const node = id => {
    if (!nodes.has(id)) nodes.set(id,{value:'',textContent:'',innerHTML:'',disabled:false,
      classList:{toggle(){}}, style:{}, addEventListener(){}, querySelectorAll(){return []}, click(){}});
    return nodes.get(id);
  };
  const context = vm.createContext({
    console, crypto:require('node:crypto').webcrypto, setTimeout,clearTimeout,
    document:{querySelector:node,querySelectorAll:()=>[]},
    window:{addEventListener(){}},location:{reload(){}}, navigator:{},
    localStorage:{getItem:k=>data.get(k)??null,setItem:(k,v)=>data.set(k,v)},
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
assert.equal(w.run('state.mode'),'questionnaire');
assert.equal(w.run('state.briefReady'),true);
w.run('save(); $("#newProject").onclick()');
assert.equal(w.run('state.order.length'),0);
const archived=JSON.parse(w.data.get('synq.live.v3.projects'));
const id=Object.keys(archived)[0];
assert.equal(archived[id].themes,old.themes);
assert.equal(archived[id].marks['E1:pricing:0'],'y');
assert.equal(w.data.get('synq.live.v2'),JSON.stringify(old));
w.run(`$("#savedProjects").value=${JSON.stringify(id)}; $("#openProject").onclick()`);
assert.equal(w.run('state.themes'),old.themes);
assert.equal(w.run('state.order[0]'),'E1');
assert.equal(w.nodes.get('#storageNotice').textContent,'');

w=workspace();
w.run('save(); state.briefDraft.project="Unsaved work"; localStorage.setItem=()=>{throw new Error("quota")}; $("#newProject").onclick()');
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
console.log('PASS: draft restoration, legacy migration, archive/open, quota recovery, cross-tab guard, evidence eligibility and output invalidation.');
