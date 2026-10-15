# Running and operating the demo

## Native services

`python scripts/demo.py` starts Grafana **12.3.6**, Prometheus **3.15.0**, Phoenix and the Python/Gradio app. Missing native binaries are downloaded from official release URLs and checked against the vendors’ SHA-256 listings. Python and Node dependencies are pinned at the top level; package lockfiles capture Node resolution.

The services use local ports **3015, 9095, 9115, 6008 and 7868**. Startup checks all five before launching. Existing unrelated services are not stopped or replaced. The native launcher’s generated configuration, logs, evidence and databases are ignored in `.runtime/`.

The Grafana login `admin / local-demo-only` is a disposable synthetic-demo credential. Anonymous viewing is Viewer only. The engine needs the local admin identity to save its exact approved dashboard patch. Never reuse this configuration on an internet-facing Grafana.

Ctrl+C stops owned native children. If an interrupted terminal left the supervisor running, identify its PID in `.runtime/owned-processes.json` and terminate that supervisor. Do not kill unrelated Grafana, Prometheus or model services.

## Ollama

The app connects to an existing local server; it does not automatically install Ollama, pull a model or write a model into your account. Configure `OI_ADVISOR_MODE=ollama`, `OLLAMA_URL` and `OLLAMA_MODEL`. Local endpoints accept only loopback or documented local container hosts.

If your model is a GGUF rather than an installed Ollama name, use Ollama’s documented local import workflow before starting the app. The recorded validation reused an existing Qwen3 4B GGUF; the model weights are not distributed in this repository.

The native API requests a structured schema with temperature zero, 8,192-token context and a bounded response. Model loading and schema support depend on your Ollama/model version. An error is visible; the app retains its independently computed rule diagnosis and never presents a fixture as a real local-model response.

No model thinking/reasoning transcript is needed. Only the structured answer, evidence references and operational measurements are retained.

### Docker with host Ollama

The Compose app uses `http://host.docker.internal:11434`. On Docker Desktop, configure your existing host Ollama so that the container can reach it through the host gateway; maintain appropriate local-only firewall/access controls. On Linux, the supplied host-gateway mapping resolves that name. If the host service cannot be reached, use the offline fixture or run the native app. The Compose file does not expose an unauthenticated model server publicly.

## Optional hosted advisor

The raw Responses API transport is manually instrumented with OpenInference; SDK auto-instrumentation is not assumed to cover a raw HTTP call.

```bash
export OI_ADVISOR_MODE=live
export GUARDIAN_MODEL=your-available-model
export OPENAI_API_KEY=your-key
python scripts/demo.py
```

Credentials are read from process environment and are not included in traces, metrics or committed configuration. Do not paste real credentials into `.env.example`. The native launcher does not automatically load `.env`; Compose uses its normal environment substitution rules.

For token-based dollar estimates, explicitly set current `OI_INPUT_USD_PER_MILLION` and `OI_OUTPUT_USD_PER_MILLION`. Without actual usage and both rates, cost stays unknown. These estimates exclude the rest of the operating bill.

## Local API

Read-only demo endpoints: `/healthz`, `/metrics`, `/api/lab/state`, `/api/lab/spans`, `/api/lab/benchmark`.

Automation mutations require `X-Investigator-Demo: synthetic-local-only`:

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/lab/demo/reset` | Restore synthetic exporter and checkout dashboard |
| POST | `/api/lab/demo/migrate` | Change the synthetic label and investigate |
| POST | `/api/lab/demo/scan` | Scan dashboard contracts |
| POST | `/api/lab/incidents/{id}/approve` | Exact `proposal_hash` and `reviewer` JSON body |
| POST | `/api/lab/incidents/{id}/reject` | Record rejection |
| POST | `/api/lab/incidents/{id}/verify` | Verify a manual repair |

The header prevents simple cross-origin browser submissions; it is not enterprise authentication. The Gradio UI and API are local demo controls. The workspace refuses a non-demo configuration. Production authentication and authorization are intentionally outside this local release.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Port occupied | Stop the older instance of this demo, or free the named port without replacing unrelated services |
| Screenshot unavailable | Install Playwright Chromium, provide `CHROME_EXECUTABLE`, or use an installed macOS Google Chrome |
| Model unconfigured / unreachable | Verify the local server, selected installed model and endpoint port |
| Phoenix has no spans | Check `/v1/traces`, `.runtime/logs/phoenix.log` and the OTLP endpoint; the local mirror remains inspectable |
| Approval is stale | A dashboard or contract changed; reset the synthetic demo or close/rescan rather than reusing the old proposal |
| Cost is unmeasured | Expected for Ollama or hosted usage without explicit rates |
| Histogram panel initially sparse | Accumulate real operations; rates and p95 need samples over the query window |
| Pytest imports unrelated plugins | Use `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` as in the README |

## Retention and resource limits

The JSONL mirror and SQLite history persist locally. The UI reads at most a 4 MiB tail and displays at most 500 spans. This is a bounded viewer, not a retention service; rotate/archive local data deliberately. Prometheus counters/histograms reset with the app process. SQLite incidents and screenshots retain workflow state across restarts.

## Upstream documentation

- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama importing GGUF models](https://docs.ollama.com/import)
- [Gradio source and documentation](https://github.com/gradio-app/gradio)
- [OpenInference instrumentation](https://github.com/Arize-ai/openinference)
- [Grafana documentation](https://grafana.com/docs/grafana/latest/)
- [Prometheus querying API](https://prometheus.io/docs/prometheus/latest/querying/api/)
