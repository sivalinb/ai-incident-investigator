# Contributing

Run the pinned local environment and `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q`. For workflow changes, also run the local integration verifier against the synthetic stack. Keep changes bounded and document what actually ran.

Preserve declared provenance: fixtures are not model calls, simulated metrics are not hardware measurements, and unknown costs are not zero-dollar totals. New model integrations need structured-output validation, real usage accounting and explicit failure behavior.

Do not introduce executable repairs based only on model output or a nonempty chart. Extend the semantic policy and live contract checks, bind approval to the exact proposed mutation and resource revision, and verify recovery. Include a meaningful regression case for any changed repair behavior.

Use bounded metric labels. Keep high-cardinality investigation details in traces/workflow records. Use fictional inputs in public screenshots and evidence artifacts. Model weights, credentials and runtime databases do not belong in source control.
