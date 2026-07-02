# Optional OTel I/O instrumentors Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let operators opt in (`PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS=1`) to the standard OpenTelemetry I/O instrumentors (botocore, requests, urllib3, httpx) so S3/HTTP calls become child spans in the trace.

**Architecture:** A new `otel/instrumentors.py` with `enable()`/`disable()` that, gated by a boolean env switch, calls `<Instrumentor>().instrument()` for every supported instrumentor that is importable. Wired into `otel/wsgi.py`'s activation block; the instrumentation packages ship via a new `opentelemetry-io` extra.

**Tech Stack:** OpenTelemetry contrib instrumentors, `plone.base.utils.boolean_value`, pytest with fakes (the real instrumentation packages are not in the test venv).

## Global Constraints

- Switch: `PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS`, boolean via `boolean_value(..., default=False)` — opt-in; truthy = enable every supported instrumentor that is importable.
- Supported (name → module → class): `botocore`→`opentelemetry.instrumentation.botocore.BotocoreInstrumentor`; `requests`→`opentelemetry.instrumentation.requests.RequestsInstrumentor`; `urllib3`→`opentelemetry.instrumentation.urllib3.URLLib3Instrumentor`; `httpx`→`opentelemetry.instrumentation.httpx.HTTPXClientInstrumentor`.
- `enable()` idempotent (module `_done` flag); each instrumentor `try/except` (skip missing/failing, debug log, never raise); remember instances for `disable()` (`uninstrument()` + reset).
- Extra `opentelemetry-io` bundles the four `opentelemetry-instrumentation-*` packages; installing it does not instrument — the switch controls activation.
- Wire `instrumentors.enable()` into `otel/wsgi.py:make_filter` in the `if provider.is_enabled():` block, after `rendering.register()`.
- Commit footer exactly: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- Run tests: `.venv/bin/pytest <path> -v`. Before committing run `uvx pre-commit run --all-files` (CI qa = ruff + ruff-format + zpretty).

## Verified facts (current code)

- `otel/wsgi.py:make_filter` `if provider.is_enabled():` block currently ends with `rendering.register()`.
- `pyproject.toml` `[project.optional-dependencies]` has `test = [...]` and `opentelemetry = ["opentelemetry-sdk", "opentelemetry-exporter-otlp", "opentelemetry-instrumentation-wsgi"]`.
- `plone.base.utils.boolean_value(value, default=...)` is used elsewhere (e.g. `provider.is_enabled`).
- How-to docs live in `docs/sources/how-to/`; `enable-opentelemetry-tracing.md` exists.
- Real `opentelemetry-instrumentation-{botocore,requests,urllib3,httpx}` are **not** installed in the test venv → tests must use fakes.

---

### Task 1: `otel/instrumentors.py`

**Files:**
- Create: `src/plone/observability/otel/instrumentors.py`
- Test: `tests/test_otel_instrumentors.py`

**Interfaces:**
- Produces: `enable()`, `disable()`, `_switch_on() -> bool`, `_load(module_path, class_name) -> instance|None`, `_SUPPORTED` (tuple of `(name, module_path, class_name)`), module lists `_enabled` / flag `_done`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_otel_instrumentors.py`:

```python
"""Tests for otel/instrumentors.py — optional OTel I/O instrumentors."""

import pytest


class _FakeInstrumentor:
    def __init__(self, fail=False):
        self.fail = fail
        self.instrumented = 0
        self.uninstrumented = 0

    def instrument(self, **kwargs):
        if self.fail:
            raise RuntimeError("nope")
        self.instrumented += 1

    def uninstrument(self, **kwargs):
        self.uninstrumented += 1


@pytest.fixture(autouse=True)
def _reset_instrumentors():
    yield
    from plone.observability.otel import instrumentors

    instrumentors.disable()


def test_switch_off_is_noop(monkeypatch):
    from plone.observability.otel import instrumentors

    monkeypatch.delenv("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", raising=False)
    instrumentors._load = lambda mp, cn: _FakeInstrumentor()  # would-be available
    instrumentors.enable()
    assert instrumentors._enabled == []


def test_switch_on_instruments_available_and_skips_missing(monkeypatch):
    from plone.observability.otel import instrumentors

    monkeypatch.setenv("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", "1")
    fakes = {
        "BotocoreInstrumentor": _FakeInstrumentor(),
        "RequestsInstrumentor": _FakeInstrumentor(),
    }
    monkeypatch.setattr(instrumentors, "_load", lambda mp, cn: fakes.get(cn))

    instrumentors.enable()

    assert fakes["BotocoreInstrumentor"].instrumented == 1
    assert fakes["RequestsInstrumentor"].instrumented == 1
    assert set(instrumentors._enabled) == set(fakes.values())


def test_enable_is_idempotent(monkeypatch):
    from plone.observability.otel import instrumentors

    monkeypatch.setenv("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", "1")
    fake = _FakeInstrumentor()
    monkeypatch.setattr(
        instrumentors, "_load",
        lambda mp, cn: fake if cn == "BotocoreInstrumentor" else None,
    )

    instrumentors.enable()
    instrumentors.enable()
    assert fake.instrumented == 1


def test_failing_instrumentor_is_skipped(monkeypatch):
    from plone.observability.otel import instrumentors

    monkeypatch.setenv("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", "1")
    boom = _FakeInstrumentor(fail=True)
    ok = _FakeInstrumentor()
    mapping = {"BotocoreInstrumentor": boom, "RequestsInstrumentor": ok}
    monkeypatch.setattr(instrumentors, "_load", lambda mp, cn: mapping.get(cn))

    instrumentors.enable()  # must not raise

    assert ok.instrumented == 1
    assert boom not in instrumentors._enabled
    assert ok in instrumentors._enabled


def test_disable_uninstruments_and_allows_reenable(monkeypatch):
    from plone.observability.otel import instrumentors

    monkeypatch.setenv("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", "1")
    fake = _FakeInstrumentor()
    monkeypatch.setattr(
        instrumentors, "_load",
        lambda mp, cn: fake if cn == "BotocoreInstrumentor" else None,
    )

    instrumentors.enable()
    instrumentors.disable()
    assert fake.uninstrumented == 1
    assert instrumentors._enabled == []

    instrumentors.enable()  # _done was reset
    assert fake.instrumented == 2


def test_switch_on_parses_env(monkeypatch):
    from plone.observability.otel import instrumentors

    monkeypatch.setenv("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", "true")
    assert instrumentors._switch_on() is True
    monkeypatch.setenv("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", "0")
    assert instrumentors._switch_on() is False
    monkeypatch.delenv("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", raising=False)
    assert instrumentors._switch_on() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_otel_instrumentors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plone.observability.otel.instrumentors'`.

- [ ] **Step 3: Write the module**

Create `src/plone/observability/otel/instrumentors.py`:

```python
"""Optional standard OpenTelemetry I/O instrumentors.

When ``PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS`` is truthy, enable every supported
instrumentor whose package is installed, so S3 (botocore) and outbound HTTP
(requests/urllib3/httpx) calls become child spans in the current trace. Opt-in;
gated by the same OTel activation as the rest of the package.
"""

from plone.base.utils import boolean_value

import importlib
import logging
import os


logger = logging.getLogger(__name__)

_SUPPORTED = (
    ("botocore", "opentelemetry.instrumentation.botocore", "BotocoreInstrumentor"),
    ("requests", "opentelemetry.instrumentation.requests", "RequestsInstrumentor"),
    ("urllib3", "opentelemetry.instrumentation.urllib3", "URLLib3Instrumentor"),
    ("httpx", "opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor"),
)

_enabled = []  # instrumentor instances we called instrument() on
_done = False


def _switch_on():
    return boolean_value(
        os.environ.get("PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS", ""), default=False
    )


def _load(module_path, class_name):
    """Return an instrumentor instance, or None if its package is absent."""
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)()
    except Exception:
        return None


def enable():
    """Instrument every supported, importable I/O library. Idempotent, opt-in."""
    global _done
    if _done or not _switch_on():
        return
    _done = True
    for name, module_path, class_name in _SUPPORTED:
        inst = _load(module_path, class_name)
        if inst is None:
            continue
        try:
            inst.instrument()
        except Exception:
            logger.debug("instrumentor %s failed to instrument", name, exc_info=True)
            continue
        _enabled.append(inst)
        logger.info("plone.observability enabled OTel instrumentor: %s", name)


def disable():
    """Uninstrument everything enable() installed and reset state."""
    global _done
    while _enabled:
        inst = _enabled.pop()
        try:
            inst.uninstrument()
        except Exception:
            pass
    _done = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/test_otel_instrumentors.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Lint + commit**

```bash
uvx pre-commit run --files src/plone/observability/otel/instrumentors.py tests/test_otel_instrumentors.py
git add src/plone/observability/otel/instrumentors.py tests/test_otel_instrumentors.py
git commit -m "feat(otel): optional I/O instrumentors module (#50)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```
(Check the commit's own exit code.)

---

### Task 2: Wire activation + extra + docs + news

**Files:**
- Modify: `src/plone/observability/otel/wsgi.py`
- Modify: `pyproject.toml`
- Modify: `docs/sources/how-to/enable-opentelemetry-tracing.md`
- Create: `news/50.feature`

**Interfaces:**
- Consumes: `instrumentors.enable()` (Task 1).

- [ ] **Step 1: Wire into the WSGI filter**

In `src/plone/observability/otel/wsgi.py`, add the import next to the others:

```python
from plone.observability.otel import instrumentors
```

and call it in the `if provider.is_enabled():` block, after `rendering.register()`:

```python
    if provider.is_enabled():
        provider.setup_tracing()
        zodb.register()
        catalog.instrument_catalog()
        subrequest.register()
        rendering.register()
        instrumentors.enable()
```

- [ ] **Step 2: Add the `opentelemetry-io` extra**

In `pyproject.toml`, after the `opentelemetry = [...]` group in `[project.optional-dependencies]`, add:

```toml
opentelemetry-io = [
    "opentelemetry-instrumentation-botocore",
    "opentelemetry-instrumentation-requests",
    "opentelemetry-instrumentation-urllib3",
    "opentelemetry-instrumentation-httpx",
]
```

- [ ] **Step 3: Add the how-to section**

Append to `docs/sources/how-to/enable-opentelemetry-tracing.md`:

```markdown
## External I/O spans (S3, HTTP)

By default only this package's own spans are emitted. To also trace external I/O — S3 blob
access (botocore/boto3) and outbound HTTP (requests/urllib3/httpx) — install the instrumentor
packages and switch them on:

```bash
pip install "plone.observability[opentelemetry,opentelemetry-io]"
export PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS=1
```

Every supported instrumentor whose package is installed is enabled; those calls then appear as
child spans nested under the active request/publish/render span. Note that `requests` uses
`urllib3` internally, so with both enabled a single requests call produces a `requests` span
*and* a nested `urllib3` span — install only the instrumentor you want if that is noisy.
```

- [ ] **Step 4: Create the news fragment**

Create `news/50.feature`:

```
Optionally enable the standard OpenTelemetry I/O instrumentors (botocore, requests, urllib3, httpx) via ``PLONE_OBSERVABILITY_OTEL_INSTRUMENTORS=1`` so S3 blob access and outbound HTTP become child spans in the same trace. Install the instrumentation packages via the new ``opentelemetry-io`` extra.
```

- [ ] **Step 5: Full suite + lint**

Run: `.venv/bin/pytest -q` → expected all pass (the `disable()` autouse fixture keeps the switch from leaking).
Run: `uvx pre-commit run --all-files` → expected all hooks pass.

- [ ] **Step 6: Commit**

```bash
git add src/plone/observability/otel/wsgi.py pyproject.toml docs/sources/how-to/enable-opentelemetry-tracing.md news/50.feature
git commit -m "feat(otel): activate I/O instrumentors + opentelemetry-io extra (#50)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Boolean switch, default off, all-available → Task 1 `_switch_on`/`enable` + `test_switch_off_is_noop`/`test_switch_on_instruments_available_and_skips_missing`/`test_switch_on_parses_env`. ✓
- Four supported instrumentors (exact modules/classes) → Task 1 `_SUPPORTED`. ✓
- Idempotent, per-instrumentor try/except, remember for disable → Task 1 + idempotency/failing/disable tests. ✓
- Extra `opentelemetry-io` (install ≠ instrument) → Task 2 Step 2. ✓
- Wire into activation after `rendering.register()` → Task 2 Step 1. ✓
- Edge cases (requests/urllib3 overlap) documented → Task 2 Step 3. ✓
- News fragment → Task 2 Step 4. ✓

**Placeholder scan:** none.

**Type consistency:** `enable()`, `disable()`, `_switch_on() -> bool`, `_load(module_path, class_name)`, `_SUPPORTED` `(name, module_path, class_name)`, `_enabled`, `_done` — consistent across Task 1 module, its tests, and the Task 2 wiring.
