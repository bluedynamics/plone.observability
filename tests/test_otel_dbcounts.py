"""Tests for otel/dbcounts.py — per-span ZODB transfer-count attributes."""


class _Conn:
    def __init__(self, loads=0, stores=0):
        self.loads = loads
        self.stores = stores
        self.clear_args = []

    def getTransferCounts(self, clear=False):
        self.clear_args.append(clear)
        return (self.loads, self.stores)


class _App:
    def __init__(self, jar):
        self._p_jar = jar


class _Req:
    def __init__(self, conn):
        self.PARENTS = [_App(conn)] if conn is not None else []


class _Span:
    def __init__(self):
        self.attrs = {}

    def set_attribute(self, key, value):
        self.attrs[key] = value


def test_read_counts_peeks_without_reset():
    from plone.observability.otel import dbcounts

    conn = _Conn(loads=5, stores=2)
    assert dbcounts.read_counts(_Req(conn)) == (5, 2)
    assert conn.clear_args == [False]  # peek, never reset


def test_read_counts_none_without_connection():
    from plone.observability.otel import dbcounts

    assert dbcounts.read_counts(_Req(None)) is None
    assert dbcounts.read_counts(object()) is None  # no PARENTS at all


def test_annotate_sets_delta_including_zero():
    from plone.observability.otel import dbcounts

    span = _Span()
    dbcounts.annotate(span, (1, 1), (4, 1))
    assert span.attrs["plone.zodb.objects_loaded"] == 3
    assert span.attrs["plone.zodb.objects_stored"] == 0


def test_annotate_noop_on_none():
    from plone.observability.otel import dbcounts

    span = _Span()
    dbcounts.annotate(span, None, (4, 1))
    dbcounts.annotate(span, (1, 1), None)
    dbcounts.annotate(None, (1, 1), (4, 1))
    assert span.attrs == {}
