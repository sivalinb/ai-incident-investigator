"""Gradio review workspace backed by real Grafana, Prometheus and OI spans."""
import argparse
import html
import json
import os
from pathlib import Path
import threading
import time

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
import gradio as gr
from fastapi import FastAPI, Response, Request, Body, HTTPException
import uvicorn

from guardian.config import Config
from guardian.engine import Engine, Conflict
from investigator.telemetry import configure, read_spans, metrics, PANELS, INCIDENTS, LIVE_BENCHMARK, LIVE_BENCHMARK_AVAILABLE
from investigator.benchmark import run_benchmark, run_live_benchmark

CSS="""
.gradio-container {max-width:1320px!important;font-family:Inter,ui-sans-serif,system-ui!important}
.oi-hero {padding:28px 30px;background:linear-gradient(120deg,#102a34,#0b1728);border:1px solid #284554;border-radius:16px;margin:4px 0 18px;color:#e7f6f4}
.oi-kicker {font-size:11px;letter-spacing:.2em;font-weight:750;color:#6de4cc;margin-bottom:12px}
.oi-hero h1 {font-size:36px!important;letter-spacing:-.035em;line-height:1.15;margin:0 0 10px!important;color:#f3fffc!important}
.oi-hero p {max-width:760px;color:#b5cbd2;line-height:1.6;font-size:15px}
.oi-badges {display:flex;flex-wrap:wrap;gap:8px;margin-top:17px}.oi-badges span{font-size:11px;border:1px solid #355461;border-radius:99px;padding:6px 10px;color:#bcece1}
.oi-links {display:flex;gap:20px;flex-wrap:wrap;margin:12px 0 18px}.oi-links a{color:#50cbb0!important;text-decoration:none;font-size:13px}
.oi-stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:4px 0 18px}.oi-stat{border:1px solid #2b3d4c;border-radius:12px;padding:16px;background:#111d2b}.oi-stat b{display:block;font-size:27px;color:#e5faf4}.oi-stat span{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#99aebc}
.oi-trace {background:#0d1826;border:1px solid #2b3d4c;padding:18px;border-radius:12px;overflow:auto;color:#cedce4}.oi-trace-row{display:flex;gap:14px;min-width:540px;align-items:center;padding:8px 0;border-bottom:1px solid #1c2c3b}.oi-kind{font-size:10px;min-width:64px;color:#70e1c6;font-weight:700}.oi-span-name{flex:1;font-family:ui-monospace,monospace;font-size:12px}.oi-ms{font-size:11px;color:#a4b7c4}.oi-bar{height:5px;background:#48bfa2;min-width:3px;border-radius:3px}
footer{display:none!important} .oi-note{font-size:12px;color:#99aebc;line-height:1.6}
@media(max-width:650px){.oi-hero h1{font-size:27px!important}.oi-stats{grid-template-columns:repeat(2,1fr)}.oi-hero{padding:22px}}
"""


def waterfall(rows):
    if not rows:
        return '<div class="oi-trace">Run an investigation to collect real OpenInference spans.</div>'
    ids={r["span_id"]:r for r in rows}
    start=min(r["start_ns"] for r in rows)
    duration=max(1,max(r["end_ns"] for r in rows)-start)
    def depth(row):
        n=0;seen=set()
        while row.get("parent_id") in ids and row["parent_id"] not in seen:
            seen.add(row["parent_id"]);row=ids[row["parent_id"]];n+=1
        return min(n,7)
    lines=['<div class="oi-trace">']
    for row in rows:
        width=max(1,round((row["end_ns"]-row["start_ns"])/duration*180))
        kind=row["attributes"].get("openinference.span.kind","SPAN")
        lines.append(f'<div class="oi-trace-row" style="padding-left:{depth(row)*14}px"><span class="oi-kind">{html.escape(kind)}</span><span class="oi-span-name">{html.escape(row["name"])}</span><span class="oi-bar" style="width:{width}px"></span><span class="oi-ms">{row["duration_ms"]:,.1f} ms</span></div>')
    lines.append('</div>')
    return ''.join(lines)


class Workspace:
    def __init__(self,config):
        if not config.demo:
            raise ValueError("The Gradio workspace supports the synthetic local demo only. Team/production use requires authenticated reviewer integration.")
        self.config=config
        self.provider=configure(config.data_dir,os.environ.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"))
        self.engine=Engine(config)
        self.report_dir=config.data_dir/"reports"
        self.report_dir.mkdir(exist_ok=True)
        self.benchmark=run_benchmark(self.report_dir)
        live_path=self.report_dir/'live-benchmark.json'
        self.live_report=json.loads(live_path.read_text()) if live_path.is_file() else None
        if self.live_report:
            LIVE_BENCHMARK.set(self.live_report['accuracy'])
            LIVE_BENCHMARK_AVAILABLE.set(1)

    def metrics_state(self):
        state=self.engine.snapshot()
        for name in ("healthy","expected_empty","unverified","empty","error","stale","missing_series"):
            PANELS.labels(name).set(sum(c["state"]==name for c in state["checks"]))
        for name in ("awaiting_review","resolved","rejected","closed","stale_approval","repair_failed"):
            INCIDENTS.labels(name).set(sum(i["status"]==name for i in state["incidents"]))
        return state

    def view(self,selected=None):
        state=self.metrics_state()
        incidents=state["incidents"]
        ids=[i["id"] for i in incidents]
        selected=selected if selected in ids else next((i["id"] for i in incidents if i["status"]=="awaiting_review"),ids[0] if ids else None)
        item=self.engine.store.get_incident(selected) if selected else None
        healthy=sum(c["state"] in ("healthy","expected_empty") for c in state["checks"])
        spans=read_spans(self.config.data_dir/"traces.jsonl",item.get("trace_id") if item else None)
        stats='<div class="oi-stats">'+''.join(f'<div class="oi-stat"><b>{v}</b><span>{label}</span></div>' for v,label in [(healthy,"Healthy contracts"),(sum(i["status"]=="awaiting_review" for i in incidents),"Awaiting review"),(sum(i["status"]=="resolved" for i in incidents),"Verified recoveries"),(len(spans),"Observed spans")])+'</div>'
        panel_rows=[[c["panel"],c["state"],c["owner"],c.get("reason","")] for c in state["checks"]]
        if item:
            p=item.get("proposal")
            advisor=item.get("advisor",{})
            note=advisor.get("note",advisor.get("reason",""))
            diagnosis=f'### {item["panel_title"]}\n\n**{item["status"].replace("_"," ").title()}** · {item["diagnosis"]["cause_status"]}\n\n{item["diagnosis"]["cause"]}\n\n{item["diagnosis"]["reason"]}\n\n**Advisor:** {advisor.get("mode","rules")} · {note}'
            if advisor.get("advice"):
                diagnosis+='\n\n**Model / fixture explanation:** '+advisor["advice"]["explanation"]
            if advisor.get("error"):
                diagnosis+='\n\n**Advisor error:** '+advisor["error"]
            if advisor.get("usage"):
                diagnosis+=f'\n\n**Actual usage:** {advisor["usage"].get("input_tokens","unknown")} input / {advisor["usage"].get("output_tokens","unknown")} output tokens · {advisor.get("duration_seconds",0):.2f} seconds'
            diff='- '+p["before"]+'\n+ '+p["after"] if p else 'No unique policy-validated patch. Review evidence; no automatic repair is available.'
            evidence=item["evidence"]
            def image(key):
                info=item.get(key,{})
                path=self.engine.evidence_dir/info.get("path","missing")
                return str(path) if info.get("available") and path.is_file() else None
            before,after=image("screenshot_before"),image("screenshot_after")
            rca=self.engine.report(selected)
            trace_id=item.get("trace_id","")
            trace_note=f'Investigation trace: `{trace_id}`. Review and verification create a new trace linked to this investigation, preserving the human pause.'
            path=self.report_dir/(selected+"-rca.md");path.write_text(rca)
            download=str(path)
        else:
            diagnosis='### Ready to investigate\n\nRun a healthy scan, simulate the label migration, then inspect the evidence and exact query change. The error-events panel is deliberately allowed to be empty.'
            diff='No repair pending.';evidence=[];before=after=None;rca='No investigation yet.';trace_note='Every scan emits real OpenInference spans.';download=None
        choices=[(i["panel_title"]+' · '+i["status"]+' · '+i["id"],i["id"]) for i in incidents]
        return (stats,panel_rows,gr.update(choices=choices,value=selected),diagnosis,diff,evidence,before,after,waterfall(spans),trace_note,rca,download,
                gr.update(interactive=bool(item and item["status"]=="awaiting_review" and item.get("proposal"))),
                gr.update(interactive=bool(item and item["status"]=="awaiting_review")))

    def action(self,action,selected,proposal_hash,reviewer):
        if action=="scan":self.engine.scan()
        elif action in ("migrate","reset"):self.engine.demo_control(action)
        elif action in ("approve","reject","verify"):
            if not selected:raise gr.Error("Choose an investigation first")
            actor=reviewer.strip()[:80] or "local-demo-reviewer"
            if action=="approve":self.engine.approve(selected,proposal_hash,actor,"Approved exact proposal in Gradio")
            elif action=="reject":self.engine.reject(selected,actor,"Rejected in Gradio")
            else:self.engine.verify_manual(selected,actor)
        return self.view(selected if action not in ("migrate","reset") else None)


def build(workspace):
    cfg=workspace.config
    grafana=os.environ.get("OI_GRAFANA_PUBLIC_URL",cfg.grafana_url).rstrip("/")
    phoenix=os.environ.get("OI_PHOENIX_PUBLIC_URL","http://127.0.0.1:6008")
    def present_live(report):
        if not report:
            return 'No live local-model evaluation has been run yet.',[],None
        summary=f'**{report.get("model","Local model")}** · **{report["correct"]}/{report["cases"]} cases passed** · {report["input_tokens"]:,} input / {report["output_tokens"]:,} output tokens. Actual local inference on authored cases; compute cost is unmeasured.'
        rows=[[r['scenario'],r['expected'],r.get('prediction',{}).get('diagnosis',r.get('error','unknown')),'Pass' if r['correct'] else 'Fail',
               (r.get('usage') or {}).get('input_tokens'),(r.get('usage') or {}).get('output_tokens'),round(r.get('duration_seconds',0),3)] for r in report['rows']]
        return summary,rows,report
    with gr.Blocks(title="AI Incident Investigator",analytics_enabled=False) as demo:
        gr.HTML('<div class="oi-hero"><div class="oi-kicker">AI INCIDENT INVESTIGATOR / LOCAL RELIABILITY LAB</div><h1>Follow the evidence.<br>Understand the investigator.</h1><p>Break a real Grafana panel, inspect the agent’s trace, review an exact repair, and verify recovery. One workflow connects infrastructure evidence to AI reliability.</p><div class="oi-badges"><span>OpenInference + OpenTelemetry</span><span>Real Grafana &amp; Prometheus</span><span>Human review</span><span>Synthetic checkout workload</span></div></div>')
        gr.HTML(f'<div class="oi-links"><a href="{grafana}/d/guardian-checkout" target="_blank">↗ Checkout dashboard</a><a href="{grafana}/d/incident-investigator" target="_blank">↗ Investigator dashboard</a><a href="{phoenix}" target="_blank">↗ Phoenix traces</a><a href="https://github.com/sivalinb/ai-incident-investigator" target="_blank">↗ Source &amp; workflow guide</a></div>')
        stats=gr.HTML()
        selected=gr.State(None)
        displayed_hash=gr.State("")
        with gr.Tab("Investigation lab"):
            with gr.Row():
                scan=gr.Button("1 · Scan contracts",variant="secondary")
                migrate=gr.Button("2 · Simulate label migration",variant="primary",interactive=cfg.demo)
                reset=gr.Button("Reset synthetic demo",interactive=cfg.demo)
                refresh=gr.Button("Refresh evidence")
            panels=gr.Dataframe(headers=["Panel","Contract state","Owner","Note"],interactive=False,label="Monitoring contracts",wrap=True)
            investigation=gr.Dropdown(label="Investigation",choices=[],interactive=True)
            with gr.Row():
                with gr.Column(scale=5):
                    diagnosis=gr.Markdown()
                    diff=gr.Code(label="Exact policy-validated query change",interactive=False)
                    reviewer=gr.Textbox(label="Local demo reviewer",value="local-demo-reviewer",info="Local prototype identity, not an authenticated team account.")
                    with gr.Row():
                        approve=gr.Button("3 · Approve exact repair",variant="primary",interactive=False)
                        reject=gr.Button("Reject proposal",interactive=False)
                        verify=gr.Button("Verify manual fix")
                with gr.Column(scale=4):
                    before=gr.Image(label="Real Grafana panel · before",interactive=False,type="filepath")
                    after=gr.Image(label="Real Grafana panel · recovered",interactive=False,type="filepath")
            with gr.Accordion("Collected evidence and candidate test results",open=False):evidence=gr.JSON(label="Evidence bundle")
        with gr.Tab("Trace explorer"):
            trace_note=gr.Markdown()
            flow=gr.HTML()
            gr.Markdown("Durations are actual local operation times. An authored offline advisor uses a CHAIN span; only real model calls use LLM spans and provider-reported tokens. Open Phoenix to inspect span attributes and linked review traces.")
        with gr.Tab("Benchmarks"):
            gr.Markdown("### Compare the evidence rules with a deliberately naive strategy\nSix authored cases include broken scrapes, ambiguous metric renames, wrong variables, legitimate emptiness and unsafe filter broadening. These are deterministic fixture results, separate from live local-model results.")
            bench_button=gr.Button("Run fixture benchmark")
            bench_table=gr.Dataframe(headers=["Strategy","Correct / cases","Accuracy","Median ms"],interactive=False,value=[[r["strategy"],f'{r["correct"]}/{r["cases"]}',f'{r["accuracy"]:.0%}',r["median_duration_ms"]] for r in workspace.benchmark["summary"]])
            with gr.Accordion('Inspect fixture inputs and results',open=False):
                bench_json=gr.JSON(value=workspace.benchmark,label="Recorded fixture results")
            gr.Markdown("### Live local-model evaluation\nUses your configured Ollama model. Six actual inference calls; ground-truth answers and scenario names are withheld. The score requires a correct diagnosis, valid evidence references and preserved scope.")
            live_button=gr.Button("Run local Ollama benchmark",interactive=bool(os.environ.get('OLLAMA_MODEL')))
            initial_summary,initial_rows,initial_report=present_live(workspace.live_report)
            live_summary=gr.Markdown(initial_summary)
            live_table=gr.Dataframe(headers=['Scenario','Expected','Local model diagnosis','Result','Input tokens','Output tokens','Seconds'],value=initial_rows,interactive=False,wrap=True)
            with gr.Accordion('Inspect actual local-model responses and usage',open=False):
                live_json=gr.JSON(value=initial_report,label="Actual local-model results")
        with gr.Tab("RCA & workflow"):
            gr.Markdown("### Full workflow\n1. Scan explicit panel contracts against real Grafana queries.\n2. Capture the failing panel and collect metric, scrape and change evidence.\n3. Record the advisor call and policy-validated candidate tests in OpenInference.\n4. Review the exact proposal hash and dashboard revision.\n5. Apply only that approved change and verify three fresh evaluations.\n6. Keep screenshots, linked traces and an RCA for future regression checks.")
            rca=gr.Markdown()
            download=gr.File(label="Download investigation RCA",interactive=False)
        outputs=[stats,panels,investigation,diagnosis,diff,evidence,before,after,flow,trace_note,rca,download,approve,reject]
        def persist_selection(value):
            item=workspace.engine.store.get_incident(value) if value else None
            return value,(item.get("proposal") or {}).get("hash","") if item else ""
        for button,action in [(scan,"scan"),(migrate,"migrate"),(reset,"reset"),(approve,"approve"),(reject,"reject"),(verify,"verify")]:
            def call(i,h,r,action=action):
                try:return workspace.action(action,i,h,r)
                except Exception as exc:raise gr.Error(str(exc) if isinstance(exc,Conflict) else type(exc).__name__) from exc
            event=button.click(call,[selected,displayed_hash,reviewer],outputs,concurrency_id="engine",concurrency_limit=1,api_name=action)
            event.then(persist_selection,investigation,[selected,displayed_hash])
        refresh.click(workspace.view,selected,outputs,concurrency_id="engine").then(persist_selection,investigation,[selected,displayed_hash])
        investigation.input(workspace.view,investigation,outputs,concurrency_id="engine").then(persist_selection,investigation,[selected,displayed_hash])
        def benchmark():
            report=run_benchmark(workspace.report_dir)
            return [[r["strategy"],f'{r["correct"]}/{r["cases"]}',f'{r["accuracy"]:.0%}',r["median_duration_ms"]] for r in report["summary"]],report
        bench_button.click(benchmark,None,[bench_table,bench_json],concurrency_id="engine",api_name="benchmark")
        def live_benchmark():
            workspace.live_report=run_live_benchmark(workspace.report_dir)
            return present_live(workspace.live_report)
        live_button.click(live_benchmark,None,[live_summary,live_table,live_json],concurrency_id="engine",api_name="live_benchmark")
        demo.load(workspace.view,None,outputs).then(persist_selection,investigation,[selected,displayed_hash])
    return demo


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--config",default="demo/config.json")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=7868)
    args=parser.parse_args()
    if args.host not in ("127.0.0.1","localhost","0.0.0.0"):
        raise SystemExit("Use a local or container bind address")
    os.environ.setdefault("OI_ADVISOR_MODE","fixture")
    workspace=Workspace(Config.load(args.config))
    app=FastAPI(title="AI Incident Investigator")
    @app.get("/healthz")
    def health():return {"status":"ok","advisor_mode":os.environ["OI_ADVISOR_MODE"]}
    @app.get("/metrics")
    def scrape():
        workspace.metrics_state()
        return Response(metrics(),media_type="text/plain; version=0.0.4")
    @app.get("/api/lab/state")
    def state():return workspace.engine.snapshot()
    @app.get("/api/lab/spans")
    def spans():return read_spans(workspace.config.data_dir/"traces.jsonl")
    @app.get("/api/lab/benchmark")
    def benchmark():return workspace.benchmark
    @app.post("/api/lab/demo/{action}")
    def demo_action(action:str,request:Request):
        if request.headers.get('X-Investigator-Demo')!='synthetic-local-only':
            raise HTTPException(403,'Explicit synthetic demo header required')
        if action not in ('reset','migrate','scan'):
            raise HTTPException(404,'Unknown demo action')
        return workspace.engine.scan() if action=='scan' else workspace.engine.demo_control(action)
    @app.post("/api/lab/incidents/{incident_id}/{action}")
    def incident_action(incident_id:str,action:str,request:Request,body:dict=Body(default={})):
        if request.headers.get('X-Investigator-Demo')!='synthetic-local-only':
            raise HTTPException(403,'Explicit synthetic demo header required')
        actor=str(body.get('reviewer','local-api-reviewer'))[:80]
        try:
            if action=='approve':return workspace.engine.approve(incident_id,str(body.get('proposal_hash','')),actor)
            if action=='reject':return workspace.engine.reject(incident_id,actor)
            if action=='verify':return workspace.engine.verify_manual(incident_id,actor)
            raise HTTPException(404,'Unknown review action')
        except Conflict as exc:raise HTTPException(409,str(exc)) from exc
    # This workspace has local prototype controls. It is not an internet-facing service.
    demo=build(workspace).queue(default_concurrency_limit=1)
    app=gr.mount_gradio_app(app,demo,path="/",allowed_paths=[str(workspace.engine.evidence_dir),str(workspace.report_dir)],
                            theme=gr.themes.Soft(primary_hue="teal",neutral_hue="slate"),css=CSS,footer_links=[])
    def scheduled():
        while True:
            try:workspace.engine.scan()
            except Exception as exc:workspace.engine.last_error=type(exc).__name__
            time.sleep(workspace.config.scan_interval_seconds)
    threading.Thread(target=scheduled,daemon=True).start()
    uvicorn.run(app,host=args.host,port=args.port,log_level="warning")


if __name__=="__main__":main()
