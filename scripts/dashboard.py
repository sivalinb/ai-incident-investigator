"""Generate a real Grafana dashboard from documented Prometheus measurements."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
DS={"type":"prometheus","uid":"guardian-prometheus"}


def build():
    panels=[]
    def panel(title,expr,x,y,w=6,h=4,kind="stat",unit="short",description=""):
        ident=len(panels)+1
        p={"id":ident,"title":title,"description":description,"type":kind,"datasource":DS,
           "gridPos":{"x":x,"y":y,"w":w,"h":h},"targets":[{"refId":"A","expr":expr,"datasource":DS,"legendFormat":"{{operation}}{{direction}}{{mode}}{{state}}","instant":kind in ("stat","gauge","bargauge")}],
           "fieldConfig":{"defaults":{"unit":unit,"color":{"mode":"palette-classic"},"thresholds":{"mode":"absolute","steps":[{"color":"green","value":None}]}},"overrides":[]},
           "options":{"colorMode":"value","graphMode":"area","reduceOptions":{"calcs":["lastNotNull"],"fields":"","values":False}}}
        panels.append(p)
        return p
    panels.append({"id":1,"title":"Read the investigation, then inspect its execution","type":"text","gridPos":{"x":0,"y":0,"w":24,"h":3},"options":{"mode":"markdown","content":"**AI INCIDENT INVESTIGATOR** · Real Grafana / Prometheus / OpenInference. Synthetic checkout workload.\n\n[Open Gradio review](http://127.0.0.1:7868) · [Inspect Phoenix spans](http://127.0.0.1:6008) · [Checkout contract](http://127.0.0.1:3015/d/guardian-checkout)\n\nOperation durations are measured. Authored fixtures never emit LLM tokens. Local inference cost is **unmeasured**; token usage is not a dollar estimate."}})
    panel("Healthy contracts",'sum(oi_panel_contexts{state=~"healthy|expected_empty"}) or vector(0)',0,3)
    panel("Waiting for review",'sum(oi_incidents{state="awaiting_review"}) or vector(0)',6,3)
    panel("Verified recoveries",'sum(oi_incidents{state="resolved"}) or vector(0)',12,3)
    panel("Actual local model calls",'sum(oi_advisor_calls_total{mode="ollama",outcome="ok"}) or vector(0)',18,3)
    panel("Investigation duration · p95",'histogram_quantile(0.95, sum by (le,operation) (rate(oi_operation_duration_seconds_bucket{operation=~"investigate|advisor.ollama|approve|grafana.screenshot"}[5m])))',0,7,12,8,"timeseries","s","Estimated from histogram buckets. Includes screenshot and verification time. No synthetic latency is inserted.")
    panel("Real model tokens",'sum by (direction) (oi_model_tokens_total)',12,7,12,8,"timeseries","short","Only provider-reported token counts from live calls; no fixtures. Counters reset with the app process.")
    panel("Operation outcomes",'sum by (operation,outcome) (oi_operations_total)',0,15,12,7,"bargauge")
    panel("Monitoring contract states",'oi_panel_contexts',12,15,12,7,"bargauge")
    panel("Fixture benchmark accuracy",'oi_benchmark_accuracy_ratio',0,22,12,6,"bargauge","percentunit","Six authored fixtures; compares deterministic strategies, not live model quality.")
    panel("Advisor provenance",'sum by (mode) (oi_advisor_calls_total)',12,22,12,6,"bargauge","short","Separate authored_fixture, ollama and hosted execution modes.")
    panel("Average operation duration",'sum by(operation)(rate(oi_operation_duration_seconds_sum[5m])) / sum by(operation)(rate(oi_operation_duration_seconds_count[5m]))',0,28,12,7,"timeseries","s")
    cost=panel("Hosted model cost estimate",'oi_model_estimated_cost_usd_total and on() (oi_model_cost_estimate_available == 1)',12,28,12,7,"stat","currencyUSD","Only appears after a hosted live call with explicit token rates. Local compute cost is unmeasured.")
    cost['fieldConfig']['defaults']['noValue']='Unmeasured'
    local=panel("Live local-model evaluation",'oi_live_benchmark_accuracy_ratio and on() (oi_live_benchmark_available == 1)',0,35,12,6,"gauge","percentunit","Actual Ollama calls on six authored cases. Ground truth is withheld from the model.")
    local['fieldConfig']['defaults']['noValue']='Not run'
    result={"uid":"incident-investigator","title":"AI Incident Investigator / Investigator Reliability","tags":["investigator","openinference"],"schemaVersion":41,"version":0,"refresh":"5s","timezone":"browser","time":{"from":"now-15m","to":"now"},"panels":panels}
    (ROOT/'observability/dashboard.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':build()
