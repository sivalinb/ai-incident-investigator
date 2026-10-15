"""Small transparent, authored benchmark. Expected answers never enter a diagnosis."""
import json
from pathlib import Path
import statistics
import time
from investigator.telemetry import operation, BENCHMARK, LIVE_BENCHMARK, LIVE_BENCHMARK_AVAILABLE

CASES=[
    {"id":"B01","name":"Label migration","evidence":{"target_up":True,"original_has_data":False,"same_metric_new_label_has_data":True,"service_filter_preserved":True,"environment_filter_preserved":True},"expected":"label_schema_drift"},
    {"id":"B02","name":"Failed scrape","evidence":{"target_up":False,"original_has_data":False,"same_metric_new_label_has_data":False},"expected":"scrape_failure"},
    {"id":"B03","name":"Renamed metric needs confirmation","evidence":{"target_up":True,"original_has_data":False,"similar_metric_present":True,"metric_alias_approved":False},"expected":"insufficient_evidence"},
    {"id":"B04","name":"Wrong dashboard variable","evidence":{"target_up":True,"original_has_data":False,"configured_service":"payments","expected_service":"checkout","same_metric_expected_service_has_data":True},"expected":"variable_mismatch"},
    {"id":"B05","name":"Legitimately empty error panel","evidence":{"target_up":True,"original_has_data":False,"allow_empty":True},"expected":"expected_empty"},
    {"id":"B06","name":"Unsafe broadening populates the chart","evidence":{"target_up":True,"original_has_data":False,"same_metric_new_label_has_data":True,"service_filter_preserved":True,"environment_filter_preserved":False},"expected":"insufficient_evidence"},
]


def classify(evidence, strategy="evidence_rules"):
    if strategy not in ("evidence_rules","naive_nonempty"):
        raise ValueError("Unknown benchmark strategy")
    if strategy=="naive_nonempty":
        return "label_schema_drift" if evidence.get("same_metric_new_label_has_data") else "scrape_failure"
    if evidence.get("allow_empty"):
        return "expected_empty"
    if evidence.get("target_up") is False:
        return "scrape_failure"
    if evidence.get("expected_service") and evidence.get("configured_service")!=evidence["expected_service"] and evidence.get("same_metric_expected_service_has_data"):
        return "variable_mismatch"
    if evidence.get("same_metric_new_label_has_data") and evidence.get("service_filter_preserved") and evidence.get("environment_filter_preserved"):
        return "label_schema_drift"
    return "insufficient_evidence"


def run_benchmark(output_dir=None):
    rows=[]
    with operation("benchmark.authored_cases","CHAIN",{"benchmark.provenance":"authored_fixture","benchmark.case_count":len(CASES)}):
        for strategy in ("evidence_rules","naive_nonempty"):
            for case in CASES:
                start=time.perf_counter()
                # Only the evidence object is passed to the classifier.
                with operation("benchmark.classify","CHAIN",{"benchmark.strategy":strategy}):
                    actual=classify(dict(case["evidence"]),strategy)
                rows.append({"case_id":case["id"],"scenario":case["name"],"strategy":strategy,"expected":case["expected"],
                             "actual":actual,"correct":actual==case["expected"],"duration_ms":round((time.perf_counter()-start)*1000,3),
                             "provenance":"authored_fixture","tokens":None,"cost_usd":None})
        summary=[]
        for strategy in ("evidence_rules","naive_nonempty"):
            group=[r for r in rows if r["strategy"]==strategy]
            accuracy=sum(r["correct"] for r in group)/len(group)
            BENCHMARK.labels(strategy).set(accuracy)
            summary.append({"strategy":strategy,"correct":sum(r["correct"] for r in group),"cases":len(group),"accuracy":accuracy,
                            "median_duration_ms":statistics.median(r["duration_ms"] for r in group)})
    report={"schema_version":1,"provenance":"authored_fixture","note":"Six transparent fixtures compare two deterministic strategies. These scores do not measure a live LLM or production accuracy. Durations include local tracing overhead.","summary":summary,"rows":rows}
    if output_dir:
        path=Path(output_dir)/"benchmark.json"
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(report,indent=2)+"\n")
    return report


def run_live_benchmark(output_dir=None):
    from investigator.ollama import chat
    labels=["label_schema_drift","scrape_failure","variable_mismatch","expected_empty","insufficient_evidence"]
    schema={"type":"object","additionalProperties":False,"properties":{
        "diagnosis":{"type":"string","enum":labels},"executable_repair":{"type":"boolean"},
        "explanation":{"type":"string"},"evidence_fields":{"type":"array","items":{"type":"string"}}},
        "required":["diagnosis","executable_repair","explanation","evidence_fields"]}
    instruction=("Classify a monitoring problem using only the evidence fields. A policy-approved label repair requires live data plus both service_filter_preserved and environment_filter_preserved true. A similar metric name alone does not establish an approved semantic alias. An allow_empty contract can make an empty panel healthy. Cite only provided evidence field names. Return the schema JSON. Do not invent missing evidence.")
    rows=[]
    with operation("benchmark.local_model","CHAIN",{"benchmark.provenance":"live_local_inference","benchmark.case_count":len(CASES)}):
        for case in CASES:
            start=time.perf_counter()
            try:
                result=chat([{"role":"system","content":instruction},{"role":"user","content":json.dumps(case["evidence"])}],schema,"benchmark.ollama")
                prediction=result.pop("output")
                fields=prediction.get("evidence_fields",[])
                citations=bool(fields) and all(isinstance(f,str) and f in case["evidence"] for f in fields)
                scope=(not prediction.get("executable_repair") or (case["evidence"].get("same_metric_new_label_has_data") and case["evidence"].get("service_filter_preserved") and case["evidence"].get("environment_filter_preserved")))
                correct=prediction.get("diagnosis")==case["expected"] and citations and bool(scope)
                row={"case_id":case["id"],"scenario":case["name"],"expected":case["expected"],"prediction":prediction,"correct":bool(correct),"citations_valid":citations,"scope_preserved":bool(scope),**result}
            except Exception as exc:
                row={"case_id":case["id"],"scenario":case["name"],"expected":case["expected"],"correct":False,"error":type(exc).__name__,"duration_seconds":time.perf_counter()-start}
            with operation("benchmark.score","EVALUATOR",{"input.value":json.dumps({"case":case["id"],"prediction":row.get("prediction")}),"output.value":json.dumps({"correct":row["correct"]}),"evaluations.0.name":"correctness","evaluations.0.score":float(row["correct"]),"evaluations.0.annotator_kind":"CODE"}):
                pass
            rows.append(row)
    accuracy=sum(r["correct"] for r in rows)/len(rows)
    LIVE_BENCHMARK.set(accuracy)
    LIVE_BENCHMARK_AVAILABLE.set(1)
    report={"schema_version":1,"provenance":"live_local_inference","model":next((r.get("model") for r in rows if r.get("model")),None),
            "correct":sum(r["correct"] for r in rows),"cases":len(rows),"accuracy":accuracy,
            "input_tokens":sum((r.get("usage") or {}).get("input_tokens",0) for r in rows),
            "output_tokens":sum((r.get("usage") or {}).get("output_tokens",0) for r in rows),
            "note":"Six authored evidence cases, measured local inference. Expected answers and scenario names are withheld from the model. No claim of production accuracy. Local compute cost is unmeasured.","rows":rows}
    if output_dir:
        path=Path(output_dir)/"live-benchmark.json";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2)+'\n')
    return report
