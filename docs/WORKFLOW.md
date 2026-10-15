# Full workflow and screenshot tour

## 1. Establish the monitoring contract

Start the stack and open Gradio. Select **Scan contracts**. The scanner reads the dashboard’s saved queries with explicit service/environment variable values and uses real Grafana data-source requests.

The queue-depth, request-rate and latency panels expect data. The error-events panel has `allow_empty: true`. Zero is a valid measurement; an empty result is different from zero. Empty panels without a declared expectation or healthy baseline remain unverified.

![Healthy Gradio workspace](screenshots/01-gradio-healthy.jpg)

## 2. Introduce the fault

Choose **Simulate label migration**. Only the local synthetic exporter changes. Its queue-depth series moves from:

```promql
guardian_checkout_queue_depth{app="checkout",environment="prod"}
```

to the same metric with `service="checkout"`. Prometheus observes the changed label set on the next scrape. The original instant panel query becomes empty; historical samples remain in Prometheus.

The scanner retains an incident fingerprint for the panel/context, preventing a new incident on every scan. Rejected incidents suppress repeated investigations until recovery or an explicit reset/close.

## 3. Collect evidence before requesting advice

The engine saves the original dashboard revision, panel context, original query evaluation and real Grafana screenshot. It collects metric metadata, live scrape-target health, bounded recent changes and a candidate query result.

Change records provide context. They do not independently prove causation. The candidate test checks that the configured semantic label alias restores the panel contract while retaining service, environment, metric and aggregation.

The configured advisor receives bounded evidence. Ollama does not receive the rule’s diagnosis or a repair write tool. Its structured response must cite existing evidence IDs. A model failure is visible and never silently replaced by a fixture.

![Review workspace](screenshots/02-gradio-review.jpg)

## 4. Inspect the investigator

Open **Trace explorer** or Phoenix. The investigation contains `AGENT`, `CHAIN`, `TOOL` and, for real inference, `LLM` spans. Screenshot and query timings are measured. The offline advisor uses a `CHAIN` span and reports no token usage.

The Gradio trace tree is a bounded local mirror of the same completed SDK spans exported over OTLP to Phoenix. Parent/span IDs preserve nesting. The model span contains the model name, supported inputs/outputs and provider-reported usage; masking settings apply before both exports.

![OpenInference trace tree](screenshots/04-openinference-trace.jpg)

## 5. Review an exact proposal

The displayed diff changes one target query. The proposal SHA-256 binds its before/after expression, target/refId, panel, context, dashboard snapshot/revision, contract hash and candidate results.

The user’s Gradio session retains the displayed hash. **Approve exact repair** submits that value. The engine reloads Grafana, checks the snapshot and contract, retests the candidate, records the reviewer and saves that one change. A changed dashboard or contract makes the approval stale.

**Reject proposal** records a rejection and leaves Grafana untouched. **Verify manual fix** checks an independently saved repair. Scheduled checks can also observe external recovery.

## 6. Verify recovery and retain the RCA

After saving, the engine performs three current query evaluations. It verifies the saved dashboard has not changed again. It captures a recovered panel and writes an RCA with evidence, query diff, reviewer, timeline and prevention suggestions.

A failed verification triggers rollback only if the dashboard still matches the agent’s saved revision. An intervening edit is preserved and the incident requires review.

Successful repair establishes recovery. It does not prove every contributing root cause. The RCA records that distinction.

![Recovered Gradio workspace](screenshots/03-gradio-recovered.jpg)

Human review may happen much later than diagnosis. Review/repair runs in a **new trace with a Span Link** to the investigation rather than holding an artificial multi-hour span open. The incident ID connects workflow history across that pause.

## 7. Inspect system-level measurements

Open Grafana’s **Investigator Reliability** dashboard. Compare operation durations, contract states, advisor provenance and actual token counts. The checkout dashboard shows the repaired measurement. Phoenix provides per-request details; Grafana provides the aggregate view.

![Grafana investigator reliability](screenshots/05-grafana-investigator.jpg)

![Phoenix trace backend](screenshots/06-phoenix-traces.jpg)

## 8. Evaluate with declared provenance

The fixture benchmark compares evidence rules against a deliberately naive strategy on six authored cases. The separate Ollama benchmark performs six real local calls with expected answers withheld. It checks classification, evidence-field references and scope preservation.

![Local model evaluation](screenshots/07-local-model-benchmark.jpg)

Recorded outputs are in [`evidence/`](evidence/). These are synthetic infrastructure cases and a small engineering benchmark, not a production accuracy claim.
