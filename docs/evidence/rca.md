# Monitoring failure RCA: Checkout queue depth

- Incident: `9bf75b440d18`
- Dashboard: Checkout · Production
- Panel ID: 1
- Status: resolved
- Detected: 2026-10-15T03:06:10.189+00:00
- Resolved: 2026-10-15T03:08:08.938+00:00
- Reviewer: local-demo-reviewer
- Context: `{"environment": "prod", "service": "checkout"}`

## Findings

The panel uses the obsolete 'app' label matcher; live telemetry responds to 'service'.

Cause status: **repair_verified**.
A successful repair confirms recovery; it does not by itself prove every contributing cause.

## Repair

```diff
- guardian_checkout_queue_depth{app="$service",environment="$environment"}
+ guardian_checkout_queue_depth{service="$service",environment="$environment"}
```

Proposal SHA-256: `f5777d715d027901c697a6b0008d8beca9e9cd2b59e2a3da90a64a4833900a57`

## Evidence

### e1: Original query evaluation

```json
{
  "state": "empty",
  "queries": [
    {
      "state": "empty",
      "series": 0,
      "points": 0,
      "labels": [],
      "last_timestamp_ms": null,
      "query": "guardian_checkout_queue_depth{app=\"checkout\",environment=\"prod\"}",
      "ref_id": "A",
      "from_ms": 1792033270183,
      "to_ms": 1792033570183,
      "datasource_uid": "guardian-prometheus"
    }
  ]
}
```

### e2: Recent changes (context, not proof by itself)

```json
[
  {
    "at": "2026-10-15T03:03:17.376592+00:00",
    "service": "checkout",
    "environment": "prod",
    "deployment": "checkout-exporter-v2",
    "change": "Queue-depth label renamed from app to service"
  },
  {
    "at": "2026-10-15T03:04:25.349657+00:00",
    "service": "checkout",
    "environment": "prod",
    "deployment": "checkout-exporter-v1",
    "change": "Restored app label for synthetic demo"
  },
  {
    "at": "2026-10-15T03:06:07.167665+00:00",
    "service": "checkout",
    "environment": "prod",
    "deployment": "checkout-exporter-v2",
    "change": "Queue-depth label renamed from app to service"
  }
]
```

### e3: Metric type and help text

```json
{
  "metric": "guardian_checkout_queue_depth",
  "metadata": [
    {
      "type": "gauge",
      "unit": "",
      "help": "Pending synthetic checkout jobs."
    }
  ]
}
```

### e4: Live scrape target health

```json
[
  {
    "metric": {
      "__name__": "up",
      "instance": "127.0.0.1:9115",
      "job": "checkout"
    },
    "value": [
      1792033578.264,
      "1"
    ]
  }
]
```

### e5: Live candidate test: app → service

```json
{
  "state": "healthy",
  "queries": [
    {
      "state": "healthy",
      "series": 1,
      "points": 1,
      "labels": [
        {
          "__name__": "guardian_checkout_queue_depth",
          "environment": "prod",
          "instance": "127.0.0.1:9115",
          "job": "checkout",
          "service": "checkout"
        }
      ],
      "last_timestamp_ms": 1792033578268,
      "query": "guardian_checkout_queue_depth{service=\"checkout\",environment=\"prod\"}",
      "ref_id": "A",
      "from_ms": 1792033278268,
      "to_ms": 1792033578268,
      "datasource_uid": "guardian-prometheus"
    }
  ]
}
```

## Verification

```json
{
  "state": "healthy",
  "queries": [
    {
      "state": "healthy",
      "series": 1,
      "points": 1,
      "labels": [
        {
          "__name__": "guardian_checkout_queue_depth",
          "environment": "prod",
          "instance": "127.0.0.1:9115",
          "job": "checkout",
          "service": "checkout"
        }
      ],
      "last_timestamp_ms": 1792033685105,
      "query": "guardian_checkout_queue_depth{service=\"checkout\",environment=\"prod\"}",
      "ref_id": "A",
      "from_ms": 1792033385105,
      "to_ms": 1792033685105,
      "datasource_uid": "guardian-prometheus"
    }
  ]
}
```

## Timeline

- 2026-10-15T03:06:10.189+00:00 — detected: {"state": "empty", "panel_id": 1}
- 2026-10-15T03:06:18.249+00:00 — evidence_captured: {"screenshot": true}
- 2026-10-15T03:06:22.505+00:00 — diagnosed: {"category": "label_schema_drift", "executable_patch": true, "model_used": true}
- 2026-10-15T03:06:22.506+00:00 — review_requested: {"proposal_hash": "f5777d715d027901c697a6b0008d8beca9e9cd2b59e2a3da90a64a4833900a57"}
- 2026-10-15T03:08:03.021+00:00 — approved: {"actor": "local-demo-reviewer", "hash": "f5777d715d027901c697a6b0008d8beca9e9cd2b59e2a3da90a64a4833900a57", "dashboard_version": 2, "note": "Approved exact proposal in Gradio"}
- 2026-10-15T03:08:03.033+00:00 — patch_applied: {"version": 3, "ref_id": "A"}
- 2026-10-15T03:08:08.939+00:00 — recovery_verified: {"actor": "local-demo-reviewer", "reason": "Approved agent repair verified on three fresh evaluations", "state": "healthy"}

## Prevention actions

- Test this panel query after exporter or collector changes.
- Keep label migration policies aligned with the instrumentation contract.
- Track source-sample freshness and expected service/environment dimensions.

Suggested regression check: rerun the repaired query with this context after instrumentation deployments.
The prevention actions are recommendations; no application instrumentation was changed.
