const $=id=>document.getElementById(id);
const stageButtons=[...document.querySelectorAll('[data-stage]')];
let evidence;
const stages=[
  {tag:'CONTRACTS',title:'An empty panel can be healthy.',description:'Three checkout panels expect data. The error-events panel explicitly allows emptiness. Monitoring starts with a contract about what should be present.',image:'01-gradio-healthy.jpg',caption:'Actual Gradio workspace · healthy baseline',query:'before',note:'Zero is a valid measurement. Expected emptiness and missing telemetry are different states.'},
  {tag:'ACTUAL FAILURE',title:'A label changes. The panel loses data.',description:'The synthetic exporter changes app="checkout" to service="checkout". The original Grafana query stops matching. The investigator captures the real panel and tests the available evidence.',image:'02-gradio-review.jpg',caption:'Actual Gradio capture · original Grafana panel says No data',query:'before',note:'Recent deployment information is context; the live candidate test provides additional evidence.'},
  {tag:'EXACT REVIEW',title:'Advice is separate from permission.',description:'The local model explains the evidence. The repair engine independently validates one configured label migration. Review binds to that exact query change, panel, contract and dashboard revision.',image:'02-gradio-review.jpg',caption:'Actual local model explanation and tested repair proposal',query:'diff',note:'The model receives no write tool. A changed dashboard or contract invalidates approval.'},
  {tag:'VERIFIED RECOVERY',title:'The repair restores the intended measurement.',description:'After the exact proposal is approved in the synthetic demo, the engine saves the query change and verifies three current evaluations. A recovered screenshot, trace link and RCA preserve the outcome.',image:'03-gradio-recovered.jpg',caption:'Actual Gradio capture · recovered panel and scope-preserving query diff',query:'after',note:'The recorded reviewer is a local demo identity. Recovery does not prove every contributing root cause.'},
];
function selectStage(index,focus=false){
  const stage=stages[index];stageButtons.forEach((b,i)=>{b.setAttribute('aria-selected',String(i===index));b.tabIndex=i===index?0:-1});
  $('stage-panel').setAttribute('aria-labelledby','stage-'+index);$('stage-tag').textContent=stage.tag;$('stage-title').textContent=stage.title;$('stage-description').textContent=stage.description;$('stage-note').textContent=stage.note;
  $('stage-image').src='assets/'+stage.image;$('stage-image').alt=stage.caption;$('stage-caption').textContent=stage.caption;
  const p=evidence?.run?.proposal;
  $('stage-query').textContent=p?(stage.query==='diff'?'- '+p.before+'\n+ '+p.after:p[stage.query]):'Recorded evidence is loading.';
  $('query-label').textContent=stage.query==='diff'?'EXACT REVIEWED CHANGE':stage.query==='after'?'VERIFIED QUERY':'ORIGINAL QUERY';
  if(focus)stageButtons[index].focus();
}
stageButtons.forEach((b,index)=>{b.addEventListener('click',()=>selectStage(index));b.addEventListener('keydown',event=>{let next=index;if(event.key==='ArrowRight')next=(index+1)%4;else if(event.key==='ArrowLeft')next=(index+3)%4;else if(event.key==='Home')next=0;else if(event.key==='End')next=3;else return;event.preventDefault();selectStage(next,true)})});
function element(tag,className,text){const el=document.createElement(tag);if(className)el.className=className;if(text!==undefined)el.textContent=text;return el}
fetch('evidence.json').then(response=>{if(!response.ok)throw Error('Evidence unavailable');return response.json()}).then(data=>{
  evidence=data;selectStage(0);
  const advisor=data.run.advisor,usage=advisor.usage||{};
  $('model-latency').textContent=advisor.duration_seconds.toFixed(2)+' s';$('model-tokens').textContent=((usage.input_tokens||0)+(usage.output_tokens||0)).toLocaleString();
  $('model-score').textContent=data.live_benchmark.correct+'/'+data.live_benchmark.cases;
  $('trace-id').textContent=data.run.trace_id;
  const spans=data.spans.filter(s=>s.trace_id===data.run.trace_id).sort((a,b)=>a.start_ns-b.start_ns),ids=new Map(spans.map(s=>[s.span_id,s])),max=Math.max(1,...spans.map(s=>s.duration_ms));
  for(const span of spans){let depth=0,p=span;const seen=new Set();while(ids.has(p.parent_id)&&!seen.has(p.parent_id)){seen.add(p.parent_id);p=ids.get(p.parent_id);depth++}
    const row=element('div','trace-row');row.style.paddingLeft=(18+Math.min(depth,5)*10)+'px';row.append(element('span','trace-kind',span.attributes['openinference.span.kind']||'SPAN'),element('span','trace-name',span.name));const bar=element('span','trace-bar');bar.style.width=Math.max(2,span.duration_ms/max*90)+'px';row.append(bar,element('span','trace-time',span.duration_ms.toFixed(1)+' ms'));$('trace-rows').append(row)
  }
  const bench=data.live_benchmark;$('bench-model').textContent=bench.model;$('bench-summary').textContent=`${bench.correct}/${bench.cases} passed · ${bench.input_tokens.toLocaleString()} input / ${bench.output_tokens.toLocaleString()} output tokens · actual local inference`;
  for(const result of bench.rows){const tr=element('tr');tr.append(element('td','',result.scenario),element('td','',result.expected),element('td','',result.prediction?.diagnosis||result.error),element('td',result.correct?'pass':'fail',result.correct?'Pass':'Fail'),element('td','',result.duration_seconds.toFixed(2)+' s'));$('bench-rows').append(tr)}
}).catch(()=>{$('stage-query').textContent='Open this walkthrough through its website URL, or run a local HTTP server to load the recorded evidence.';$('bench-summary').textContent='Recorded evidence could not be loaded. The full artifacts remain available in the public repository.'});
