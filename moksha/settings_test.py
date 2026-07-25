"""Hermetic settings used by the automated test suite."""

from moksha.settings import *  # noqa: F401,F403

# Django's in-process test client does not terminate TLS.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
