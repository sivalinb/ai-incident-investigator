"""Real OpenInference spans, a durable local mirror, and bounded Prometheus labels."""
from contextlib import contextmanager
from functools import wraps
import json
import os
from pathlib import Path
import threading
import time

from openinference.instrumentation import OITracer, TraceConfig
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

REGISTRY = CollectorRegistry()
OPERATIONS = Counter("oi_operations_total", "Completed observed operations.", ["operation", "kind", "outcome"], registry=REGISTRY)
DURATION = Histogram("oi_operation_duration_seconds", "Actual observed operation duration.", ["operation"], buckets=(.005,.02,.1,.5,1,2,5,10,30,60), registry=REGISTRY)
ADVISORS = Counter("oi_advisor_calls_total", "Advisor calls by explicit execution mode.", ["mode", "outcome"], registry=REGISTRY)
TOKENS = Counter("oi_model_tokens_total", "Provider-reported tokens; fixtures never contribute.", ["direction"], registry=REGISTRY)
ESTIMATED_COST = Counter("oi_model_estimated_cost_usd_total", "Usage multiplied by configured rates; excludes infrastructure.", registry=REGISTRY)
ESTIMATED_COST_AVAILABLE = Gauge("oi_model_cost_estimate_available", "One only after a real hosted call with explicit rates.", registry=REGISTRY)
PANELS = Gauge("oi_panel_contexts", "Latest scan result by panel contract state.", ["state"], registry=REGISTRY)
INCIDENTS = Gauge("oi_incidents", "Persisted investigations by workflow state.", ["state"], registry=REGISTRY)
BENCHMARK = Gauge("oi_benchmark_accuracy_ratio", "Authored fixture benchmark; not live model accuracy.", ["mode"], registry=REGISTRY)
LIVE_BENCHMARK = Gauge("oi_live_benchmark_accuracy_ratio", "Measured local model score on the six authored cases.", registry=REGISTRY)
LIVE_BENCHMARK_AVAILABLE = Gauge("oi_live_benchmark_available", "One when a persisted or new live local-model evaluation exists.", registry=REGISTRY)
_provider = None
_tracer = None
_mirror = None


class JsonlExporter(SpanExporter):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()

    def export(self, spans):
        with self.lock, self.path.open("a") as out:
            for span in spans:
                row = {
                    "name": span.name, "trace_id": format(span.context.trace_id, "032x"),
                    "span_id": format(span.context.span_id, "016x"),
                    "parent_id": format(span.parent.span_id, "016x") if span.parent else None,
                    "start_ns": span.start_time, "end_ns": span.end_time,
                    "duration_ms": round((span.end_time-span.start_time)/1e6, 3),
                    "status": span.status.status_code.name,
                    "attributes": dict(span.attributes or {}),
                    "links": [{"trace_id": format(link.context.trace_id, "032x"), "span_id": format(link.context.span_id, "016x")} for link in span.links],
                }
                out.write(json.dumps(row, default=str)+"\n")
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def configure(data_dir, endpoint=None):
    global _provider, _tracer, _mirror
    if _provider:
        return _provider
    _mirror = JsonlExporter(Path(data_dir)/"traces.jsonl")
    _provider = TracerProvider(resource=Resource.create({
        "service.name": "ai-incident-investigator", "service.version": "0.1.0",
        "openinference.project.name": "ai-incident-investigator",
    }))
    _provider.add_span_processor(SimpleSpanProcessor(_mirror))
    if endpoint:
        _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, timeout=5)))
    _tracer = OITracer(_provider.get_tracer("investigator"), config=TraceConfig(
        hide_inputs=os.environ.get("OPENINFERENCE_HIDE_INPUTS", "false").lower()=="true",
        hide_outputs=os.environ.get("OPENINFERENCE_HIDE_OUTPUTS", "false").lower()=="true",
    ))
    return _provider


def current_trace_id():
    context = trace.get_current_span().get_span_context()
    return format(context.trace_id, "032x") if context.is_valid else ""


@contextmanager
def operation(name, kind, attributes=None, links=None):
    if _tracer is None:
        yield trace.get_current_span()
        return
    attrs = {"openinference.span.kind": kind, **(attributes or {})}
    start = time.perf_counter()
    outcome = "ok"
    try:
        with _tracer.start_as_current_span(name, attributes=attrs, links=links or []) as span:
            yield span
    except Exception:
        outcome = "error"
        raise
    finally:
        OPERATIONS.labels(name, kind, outcome).inc()
        DURATION.labels(name).observe(time.perf_counter()-start)


def step(name, kind):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            links = []
            # Review is a new trace after a human pause, linked to its investigation.
            if name in ("approve", "reject", "verify_manual") and len(args)>1 and _tracer:
                try:
                    item = args[0].store.get_incident(args[1])
                    if item.get("trace_id") and item.get("investigation_span_id"):
                        context = trace.SpanContext(int(item["trace_id"],16), int(item["investigation_span_id"],16), False, trace.TraceFlags(1))
                        links = [trace.Link(context)]
                except (KeyError, ValueError, TypeError):
                    pass
            with operation(name, kind, links=links) as span:
                if name in ("approve", "reject", "verify_manual") and len(args)>1:
                    span.set_attribute("session.id", str(args[1]))
                value = fn(*args, **kwargs)
                if isinstance(value, dict):
                    if name=="investigate":
                        value["investigation_span_id"] = format(span.get_span_context().span_id,"016x")
                        span.set_attribute("session.id", value["id"])
                        span.set_attribute("metadata", json.dumps({"incident_id":value["id"],"panel_id":value["panel_id"]}))
                    state = value.get("status", value.get("state", "completed"))
                    span.set_attribute("output.value", json.dumps({"state":state,"operation":name}))
                    span.set_attribute("output.mime_type", "application/json")
                return value
        return wrapped
    return decorate


def read_spans(path, trace_id=None):
    path = Path(path)
    if not path.exists():
        return []
    # A bounded tail prevents the UI from reading an unbounded history into memory.
    with path.open("rb") as source:
        source.seek(0, 2)
        size = source.tell()
        source.seek(max(0,size-4*1024*1024))
        if size>4*1024*1024:
            source.readline()
        lines = source.read().decode().splitlines()
    rows=[]
    for line in lines:
        try:
            row=json.loads(line)
        except json.JSONDecodeError:
            continue
        if not trace_id or row["trace_id"]==trace_id:
            rows.append(row)
    return sorted(rows, key=lambda x:x["start_ns"])[-500:]


def metrics():
    return generate_latest(REGISTRY)
