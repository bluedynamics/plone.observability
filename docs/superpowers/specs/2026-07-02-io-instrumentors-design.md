# Optional OTel I/O instrumentors (botocore / requests / urllib3 / httpx)

**Date:** 2026-07-02
**Issue:** [#50](https://github.com/plone/plone.observability/issues/50)
**Status:** Approved (design)

## Summary

The OTel filter sets up the tracer but only emits the package's own spans; external I/O during
a request is invisible — **S3 blob access** (zodb-pgjsonb S3 backend via botocore/boto3) and
**outbound HTTP** (thumbor/image services via requests/urllib3/httpx). Let operators opt in to
the standard OpenTelemetry instrumentations so those calls become child spans in the same
trace. Pairs with the per-span ZODB counts/time: those show DB round-trips, this shows S3/HTTP
— together the previously-dark I/O time is attributed. (For aaf: botocore spans prove
instantly whether S3 blobs are fetched during render.)

## Decisions (locked)

- **Switch:** `PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS` — boolean, default **off** (opt-in).
  When truthy, enable **every supported instrumentor that is importable**.
- **Packaging:** a new extra `opentelemetry-io` bundles the instrumentation packages. Installing
  the extra does **not** instrument — the switch still controls activation.
- Supported: `botocore`, `requests`, `urllib3`, `httpx`.

## Components

### New `src/plone/observability/otel/instrumentors.py`

- `_SUPPORTED` — an ordered tuple of `(name, module_path, class_name)`:
  - `("botocore", "opentelemetry.instrumentation.botocore", "BotocoreInstrumentor")`
  - `("requests", "opentelemetry.instrumentation.requests", "RequestsInstrumentor")`
  - `("urllib3", "opentelemetry.instrumentation.urllib3", "URLLib3Instrumentor")`
  - `("httpx", "opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor")`
- `_switch_on()` → `boolean_value(os.environ.get("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", ""), default=False)`.
- `_load(module_path, class_name)` → import the module and return `Class()`, or `None` on any import/attr error.
- `enable()` — idempotent (module-level `_done` flag). If `_switch_on()`: for each `_SUPPORTED`
  entry, `_load` it; if present, call `.instrument()`, remember the instance in `_enabled`, and
  log at info. Per-instrumentor `try/except` → a failing one is logged at debug and skipped;
  never breaks activation.
- `disable()` — call `.uninstrument()` on each remembered instance, clear `_enabled`, reset
  `_done` (for teardown/tests).

### `otel/wsgi.py`

Call `instrumentors.enable()` in the existing `if provider.is_enabled():` block, after
`rendering.register()`.

### `pyproject.toml`

```toml
opentelemetry-io = [
    "opentelemetry-instrumentation-botocore",
    "opentelemetry-instrumentation-requests",
    "opentelemetry-instrumentation-urllib3",
    "opentelemetry-instrumentation-httpx",
]
```

## Data flow / nesting

Instrumentors are process-global, enabled once at first serve. Their spans attach to the
**current** OTel context, so S3/HTTP calls made during a request nest under the active span
(`ZPublisher.publish` / `subrequest` / `viewlet` / `portlet`). No per-request wiring.

## Edge cases (documented, not fixed)

- **requests + urllib3 overlap:** `requests` uses `urllib3`, so with both enabled a single
  requests call yields a `requests` span *and* a nested `urllib3` span. Standard OTel behaviour;
  operators who want only one install just that instrumentation package (the extra pulls all,
  but a subset can be installed without the extra).
- **Out-of-request I/O:** I/O with no active request span (cache warmer, tika-worker,
  the `@@metrics` scrape) produces root spans. Rare and generally harmless; noted.

## Error handling

`_load` and each `instrument()` are wrapped in `try/except` → a missing or misbehaving
instrumentor is skipped (debug log), never raising. `enable()` is a no-op when the switch is
off or already done.

## Testing

`tests/test_otel_instrumentors.py` — the real instrumentation packages are not in the test
venv, so use fakes:

1. **Switch off → no-op:** with the env unset, `enable()` instruments nothing (`_enabled` empty).
2. **Switch on → instrument each importable:** monkeypatch `_load` to return a fake instrumentor
   (records `instrument()`/`uninstrument()` calls) for some names and `None` for others; assert
   `instrument()` called once per available name, missing ones skipped.
3. **Idempotent:** two `enable()` calls → each fake instrumented once (`_done` guard).
4. **A failing `instrument()` is skipped**, others still enabled, no exception propagates.
5. **`disable()`** calls `uninstrument()` on each and resets state (a second `enable()` after
   `disable()` re-instruments).
6. **`_switch_on()`** parses the env var via `boolean_value` (truthy/falsy/unset).

An autouse fixture calls `instrumentors.disable()` after each test to reset the module state.

## Docs

A how-to note (README / docs): install `plone.observability[opentelemetry,opentelemetry-io]`
and set `PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS=1`; mention the requests/urllib3 overlap.

## CHANGES

Towncrier `feature` fragment:

> Optionally enable the standard OpenTelemetry I/O instrumentors (botocore, requests, urllib3,
> httpx) via ``PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS=1`` so S3 blob access and outbound HTTP
> become child spans in the same trace. Install the instrumentation packages via the new
> ``opentelemetry-io`` extra. #50
