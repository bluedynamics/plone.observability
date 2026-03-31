from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import FunctionalTesting
from plone.app.testing import IntegrationTesting
from plone.app.testing import PloneSandboxLayer

import plone.observability


class PloneObservabilityLayer(PloneSandboxLayer):
    defaultBases = (PLONE_FIXTURE,)

    def setUpZope(self, app, configurationContext):
        self.loadZCML(package=plone.observability)


PLONE_OBSERVABILITY_FIXTURE = PloneObservabilityLayer()

PLONE_OBSERVABILITY_INTEGRATION_TESTING = IntegrationTesting(
    bases=(PLONE_OBSERVABILITY_FIXTURE,),
    name="PloneObservabilityLayer:IntegrationTesting",
)

PLONE_OBSERVABILITY_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(PLONE_OBSERVABILITY_FIXTURE,),
    name="PloneObservabilityLayer:FunctionalTesting",
)
