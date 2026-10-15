# Recorded validation — October 14, 2026

## Verified locally

| Check | Observed result |
| --- | --- |
| Regression suite | **33 passed** on Python 3.12 |
| Gradio browser flow | Healthy scan → label migration → model advice → exact review → recovered panel |
| Independent API integration | **Passed**; four panel contexts, real before/after images, preserved environment scope and linked review trace |
| Grafana | Two actual dashboards with real Prometheus queries |
| OpenInference | Actual SDK spans exported over OTLP and accepted by Phoenix |
| Local inference | Existing Qwen3 4B quantized GGUF imported into task-local Ollama storage |
| Authored evidence rules | **6/6** controlled cases |
| Deliberately naive strategy | **2/6** controlled cases |
| Live Qwen3 benchmark | **3/6** in each of two measured UI runs |

The test suite covers proposal hashes, changed dashboard/contract revisions, rejection, manual repair, rollback, permissions, legitimate emptiness, unsupported panels, model-output validation, real SDK parentage/masking, real-provider usage accounting, endpoint boundaries and fixture provenance.

The browser demonstration uses the local prototype reviewer. The API verification uses `local-integration-reviewer`. These are explicitly named automated/demo identities, not evidence of authenticated production human review.

## Recorded executions

The screenshot tour and public walkthrough use browser incident **`9bf75b440d18`**, investigation trace **`76503b3f1d8d8951e1263d4ed6a76235`**. Its local model request used **797 input / 243 output tokens** and took **4.23 seconds** at the caller. The full investigation, including an actual panel screenshot, took about **12.37 seconds**. It produced a verified repaired panel and an RCA.

The independent API verifier subsequently created incident **`a7e85c13d4fd`**, trace **`75e9b89cdb0a83070a92a75874ac0e03`**. It passed the header, screenshot, proposal, recovery and Span Link assertions. Its separate result is in [`verification.json`](evidence/verification.json).

The final local-model evaluation run consumed **712 input / 968 output tokens** over six calls. The earlier run consumed **712 / 978**; both scored **3/6**. Temperature zero does not establish identical generated text across runs. Caller timings and native model timings are retained in the JSON reports.

The model misclassified the scrape failure, wrong dashboard variable and legitimate empty-panel cases in this small suite. It correctly handled the label migration, ambiguous metric rename and unsafe scope-broadening cases. The published output retains those failures. The operational repair policy never executes a query simply because the model suggested it.

## Evidence

- [Canonical browser investigation](evidence/recorded-run.json)
- [Selected real spans and linked review trace](evidence/spans.json)
- [Original panel](evidence/panel-before.png) and [recovered panel](evidence/panel-after.png)
- [Root-cause report](evidence/rca.md)
- [API integration proof](evidence/verification.json)
- [Fixture benchmark](evidence/fixture-benchmark.json)
- [Final actual Ollama evaluation](evidence/ollama-benchmark.json)
- [Earlier actual Ollama evaluation](evidence/ollama-benchmark-first.json)

## Limits

Hardware/service telemetry is synthetic. The real local model received normalized authored evidence in the six-case benchmark; this is not a production SRE accuracy estimate. The demonstration verifies a configured label migration, not arbitrary repair generation.

Docker is not installed on the local validation host. The Compose workflow is provided and separately exercised by repository CI. Check the current GitHub Actions run for its outcome; a local native pass does not itself prove the container build passed.

The raw hosted Responses API path is tested with a transport stub; no hosted model/key was configured for this validation. The live evidence comes from local Ollama. Local hardware/energy cost is unmeasured. Phoenix may show a zero hosted-model price for an unpriced local model; that is not a measurement of total operating cost.

Screenshot files are actual captures of Gradio, Grafana and Phoenix. The public website renders those recorded artifacts. It does not provide remote Gradio controls or a live model endpoint.
