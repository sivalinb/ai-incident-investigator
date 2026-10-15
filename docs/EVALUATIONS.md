# Evaluation methodology

This repository separates **a real infrastructure repair run**, **authored deterministic fixtures**, and **actual local-model evaluation**. Each output records its provenance. A small controlled demo is not a general SRE benchmark.

## A. Real Grafana break / repair / recovery

The integration run uses an actual exporter, Prometheus, Grafana dashboard revisions, headless panel images and the repair engine. It verifies:

- Declared healthy/allowed-empty contracts before the fault.
- An unexpected empty result after `app → service` migration.
- A unique configured semantic label repair with service/environment scope preserved.
- A matching displayed proposal hash and unchanged dashboard/contract before saving.
- Three current evaluations of the repaired saved dashboard.
- Before/after panel captures and an RCA.
- A real OpenInference investigation trace and linked review trace.

The fault and service workload are synthetic. The named local/integration reviewer is an automated demonstration identity, not authenticated production human approval.

## B. Six authored evidence cases

| ID | Scenario | Expected handling |
| --- | --- | --- |
| B01 | Label migration with preserved scope | Recognize label schema drift |
| B02 | Scrape target is down | Recognize scrape failure |
| B03 | Similar metric name, no approved alias | Report insufficient evidence |
| B04 | Wrong dashboard service variable | Recognize context mismatch |
| B05 | Error panel explicitly allows emptiness | Treat expected emptiness as healthy |
| B06 | Candidate drops environment scope | Decline the unsafe apparent repair |

The deterministic benchmark compares evidence rules with `naive_nonempty`, an intentionally weak strategy. That contrast demonstrates why a populated chart is not sufficient repair evidence. The fixtures include normalized evidence flags, not the full complexity of discovering those signals in a real incident.

The expected answer, scenario name and case ID never enter `classify`. Expected answers are available publicly for inspection; this is an authored teaching suite, not a held-out external dataset. Fixture durations include local tracing overhead and are not model performance measurements. Fixtures report `tokens=null` and `cost_usd=null`.

## C. Live Ollama evaluation

Choose **Run local Ollama benchmark** in Gradio after configuring an installed local model. It makes six real structured-output inference calls, passing only each evidence object. The prompt explains the available classification task and repair policy but does not supply expected answers or case names.

The code evaluator requires all three:

1. The expected diagnosis class.
2. Nonempty evidence references that name existing input fields.
3. No executable label repair without the declared metric test and preserved service/environment scope.

Results include each prediction, explanation, score, actual provider usage, caller duration and native load/generation timings. Failures remain explicit. The evaluator does not use an LLM judge. Evidence-reference validity checks existence, not whether every natural-language inference is justified; review the explanations as well as the numeric score.

The six normalized cases cannot establish production accuracy, coverage over new failures, causal proof, model robustness or repair success against arbitrary dashboards. Even a perfect score is six outcomes on this particular authored suite. No dollar total is assigned to local compute.

## Reproduction and artifacts

- `docs/evidence/fixture-benchmark.json`: recorded deterministic comparison.
- `docs/evidence/ollama-benchmark.json`: actual local-model outputs and measurements.
- `docs/evidence/recorded-run.json`: the real panel-repair investigation.
- `docs/evidence/verification.json`: integration assertions and observed outcome.
- `docs/evidence/spans.json`: selected real investigation/review spans.

To extend the suite, add a new evidence case and expected outcome independently, document its provenance and ensure the expected answer cannot enter the diagnostic input. For a serious model comparison, expand the corpus, freeze a held-out set and run repeated trials with declared model/runtime/hardware settings.
