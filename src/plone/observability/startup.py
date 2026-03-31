import logging

import Zope2
from zope.component import queryUtility

from plone.observability.health.server import HealthServer
from plone.observability.interfaces import IReadinessCheck

logger = logging.getLogger(__name__)

_health_server = HealthServer()


def on_process_starting(event):
    """Start the health server when Zope finishes startup.

    Also wires the ZODB Database reference to the health server
    and the ZODB readiness check so they can open connections
    outside the WSGI request cycle.
    """
    db = Zope2.DB
    _health_server.db = db

    # Wire the DB to the ZODB readiness check
    zodb_check = queryUtility(IReadinessCheck, name="zodb")
    if zodb_check is not None:
        zodb_check.db = db

    logger.info("Starting plone.observability health server")
    _health_server.start()
