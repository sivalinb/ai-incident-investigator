# Telemetry reference

## OpenInference spans

The app uses the real OpenTelemetry SDK and OpenInference `OITracer`. Every observation has SDK-generated IDs and monotonic/wall-clock timing. Phoenix accepts the OTLP HTTP export; the local JSONL mirror supports the Gradio trace explorer.

| Span | Kind | What it records |
| --- | --- | --- |
| `scan` | `CHAIN` | Dashboard contract scan and nested panel checks |
| `investigate` | `AGENT` | One evidence collection, diagnosis and candidate-test workflow |
| `evaluate` | `CHAIN` | Contract evaluation using actual query results |
| `grafana.get`, `grafana.query`, `grafana.prometheus` | `TOOL` | Real dashboard, data-source and Prometheus operations |
| `grafana.screenshot` | `TOOL` | Actual headless panel capture time |
| `advisor.authored_fixture` | `CHAIN` | Explicit authored offline advice, with no LLM token attributes |
| `advisor.ollama`, `benchmark.ollama` | `LLM` | Actual local model request, response and usage |
| `advisor.live` | `LLM` | Optional hosted Responses API request and reported usage |
| `approve`, `reject`, `verify_manual` | `CHAIN` | Review operation, session/incident ID and investigation Span Link |
| `grafana.save` | `TOOL` | Approved dashboard save or revision-safe rollback |
| `resolve` | `CHAIN` | Recovery capture and persisted result |
| `benchmark.score` | `EVALUATOR` | Code-scored classification, references and scope checks |

The resource identifies `service.name=ai-incident-investigator` and `openinference.project.name=ai-incident-investigator`. `openinference.span.kind` provides AI-aware operation identity. `input.value`/`output.value` describe bounded payloads; `llm.model_name` identifies actual inference. `llm.token_count.prompt` and `.completion` come from the provider, never text-length estimates.

Ollama additionally reports model load, prompt evaluation, generation and total durations in nanoseconds. Its native total does not necessarily equal the caller’s measured HTTP duration. The local benchmark retains both.

Trace links connect an asynchronously reviewed repair to the original investigation. They do not claim the human pause was active computation. The local explorer shows nested completed spans for the selected investigation; Phoenix shows individual span attributes and linked traces.

## Prometheus measurements

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `oi_operations_total` | Counter | operation, kind, outcome | Observed operation completions/errors |
| `oi_operation_duration_seconds` | Histogram | operation | Actual operation duration; nested times overlap |
| `oi_advisor_calls_total` | Counter | mode, outcome | Distinguishes fixture, Ollama and hosted calls |
| `oi_model_tokens_total` | Counter | direction | Actual reported input/output tokens |
| `oi_model_estimated_cost_usd_total` | Counter | none | Hosted usage × explicit per-million-token rates |
| `oi_model_cost_estimate_available` | Gauge | none | Whether any configured hosted estimate is available |
| `oi_panel_contexts` | Gauge | state | Latest persisted contract check states |
| `oi_incidents` | Gauge | state | Investigation workflow-state counts |
| `oi_benchmark_accuracy_ratio` | Gauge | mode | Latest authored deterministic benchmark result |
| `oi_live_benchmark_accuracy_ratio` | Gauge | none | Latest measured local-model result on the same authored cases |

Incident IDs, trace IDs, raw prompts, queries and user names are not metric labels. They belong in traces and durable workflow evidence. The label sets are bounded by implementation-defined operations/states.

Counters and histograms are process-local and reset when the Gradio process restarts. SQLite workflow state survives restart. Benchmark gauges are latest-run values. Nested operation durations should not be summed into an end-to-end request duration.

Example Grafana expressions:

```promql
sum(oi_panel_contexts{state=~"healthy|expected_empty"})
histogram_quantile(0.95,
  sum by (le,operation) (rate(oi_operation_duration_seconds_bucket[5m])))
sum by (direction) (oi_model_tokens_total)
oi_model_estimated_cost_usd_total and on()
  (oi_model_cost_estimate_available == 1)
```

An empty cost panel means **unmeasured**, not a zero-dollar total. Hosted estimates exclude caching/reasoning pricing subtleties unless the operator’s rate assumptions account for them. Ollama hardware/energy cost is not estimated.

## Payload controls

Set `OPENINFERENCE_HIDE_INPUTS=true` and/or `OPENINFERENCE_HIDE_OUTPUTS=true` before launch. `OITracer` applies masking before the JSONL mirror and OTLP export. A real SDK test verifies the redacted payloads and preserved usage counts. Application metadata, incident evidence and SQLite records have their own retention/privacy requirements; trace masking does not erase those stores.

The demo contains fictional service telemetry. Do not publish real prompts, screenshots, customer identifiers or production evidence by copying the recorded-demo export process unchanged.

## Primary references

- [OpenInference specification](https://arize-ai.github.io/openinference/spec/)
- [OpenInference configuration and masking](https://arize-ai.github.io/openinference/spec/configuration.html)
- [OpenTelemetry Python tracing](https://opentelemetry.io/docs/languages/python/instrumentation/)
- [Ollama native chat response and usage](https://docs.ollama.com/api/chat)
- [Phoenix self-hosting](https://arize.com/docs/phoenix/self-hosting)
