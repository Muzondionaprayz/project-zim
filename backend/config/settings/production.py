"""
Production settings.

DEBUG is always False. All values that matter for security are required
from the environment and the process fails fast (via python-decouple)
if they are missing, rather than silently falling back to an insecure
default.
"""

from .base import *  # noqa: F401,F403
from decouple import config

DEBUG = False

# In production, ALLOWED_HOSTS must be explicitly configured.
if not ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError(
        "DJANGO_ALLOWED_HOSTS must be set (comma-separated) when running "
        "with the production settings module."
    )

# HTTPS / transport security.
SECURE_SSL_REDIRECT = config("DJANGO_SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = config("DJANGO_SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
