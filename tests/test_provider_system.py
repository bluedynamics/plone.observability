from plone.observability.interfaces import IMetricProvider
from plone.observability.metrics.providers.system import SystemMetricProvider
from zope.interface.verify import verifyObject


class FakeApp:
    pass


class TestSystemMetricProvider:
    def test_implements_interface(self):
        provider = SystemMetricProvider(FakeApp())
        assert verifyObject(IMetricProvider, provider)

    def test_scope_is_instance(self):
        provider = SystemMetricProvider(FakeApp())
        assert provider.scope == "instance"

    def test_collects_rss_metric(self):
        provider = SystemMetricProvider(FakeApp())
        metrics = list(provider.collect())
        names = [m.name for m in metrics]
        assert "plone_process_rss_bytes" in names

    def test_collects_cpu_metric(self):
        provider = SystemMetricProvider(FakeApp())
        metrics = list(provider.collect())
        names = [m.name for m in metrics]
        assert "plone_process_cpu_seconds" in names

    def test_rss_is_positive(self):
        provider = SystemMetricProvider(FakeApp())
        metrics = {m.name: m for m in provider.collect()}
        assert metrics["plone_process_rss_bytes"].value > 0

    def test_all_metrics_are_instance_scope(self):
        provider = SystemMetricProvider(FakeApp())
        for m in provider.collect():
            assert m.scope == "instance"
