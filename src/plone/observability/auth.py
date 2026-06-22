"""Authentication detection for request metrics and tracing (no OTel import)."""

from AccessControl.SecurityManagement import getSecurityManager


ENVIRON_KEY = "plone.observability.authenticated"


def get_auth_info():
    """Return (authenticated: bool, user_id: str | None) for the current context.

    Uses CMFCore's anonymous semantics: a request is anonymous when there is no
    user or the user's name is the Zope/PAS "Anonymous User".
    """
    user = getSecurityManager().getUser()
    if user is None or user.getUserName() == "Anonymous User":
        return False, None
    return True, user.getId()
