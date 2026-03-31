from plone.observability.health.checks import ZODBReadinessCheck
from plone.observability.interfaces import IReadinessCheck
from zope.interface.verify import verifyObject


class FakeConnection:
    def __init__(self, root_data=None, raise_on_root=False):
        self._root_data = root_data or {}
        self._raise_on_root = raise_on_root
        self.closed = False

    def root(self):
        if self._raise_on_root:
            raise Exception("ZODB connection failed")
        return self._root_data

    def close(self):
        self.closed = True


class FakeDB:
    def __init__(self, connection=None):
        self._connection = connection or FakeConnection({"Application": True})

    def open(self):
        return self._connection


class TestZODBReadinessCheck:
    def test_implements_interface(self):
        check = ZODBReadinessCheck()
        check.db = FakeDB()
        assert verifyObject(IReadinessCheck, check)

    def test_ok_when_db_is_readable(self):
        check = ZODBReadinessCheck()
        check.db = FakeDB()
        ok, message = check()
        assert ok is True
        assert "ok" in message.lower()

    def test_fail_when_no_db(self):
        check = ZODBReadinessCheck()
        check.db = None
        ok, message = check()
        assert ok is False

    def test_fail_when_db_raises(self):
        conn = FakeConnection(raise_on_root=True)
        check = ZODBReadinessCheck()
        check.db = FakeDB(connection=conn)
        ok, message = check()
        assert ok is False
        assert "failed" in message.lower() or "error" in message.lower()

    def test_connection_is_closed_after_check(self):
        conn = FakeConnection()
        check = ZODBReadinessCheck()
        check.db = FakeDB(connection=conn)
        check()
        assert conn.closed is True
