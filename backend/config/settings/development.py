"""
Development settings.

Loosens a few constraints for local work. Never used in production —
production.py is selected there via the DJANGO_SETTINGS_MODULE env var.
"""

from .base import *  # noqa: F401,F403
from decouple import config

DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)

# Convenient default for local development if DJANGO_ALLOWED_HOSTS is unset.
if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

# Allow the local frontend dev server by default in development.
if not CORS_ALLOWED_ORIGINS:  # noqa: F405
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
