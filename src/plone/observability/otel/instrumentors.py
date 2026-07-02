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
