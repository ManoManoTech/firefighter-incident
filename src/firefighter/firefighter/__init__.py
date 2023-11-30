"""This is the main entrypoint for FireFighter.

!!! warning

    This app does not contain any business logic. It is responsible for loading all the settings, providing common base features and tying together all the other apps.

## Features

- Load all settings
- Provide `ASGI` and `WSGI` entrypoints
- Configure loggers
- Provide a Celery app
- Set the base URL routing
- Provides a `healthcheck` endpoint
- Provide a `robots.txt` endpoint
- Provides some utils
- Provides SSO integration
- Register the Django admin and customize its theme

"""

from __future__ import annotations

from firefighter.firefighter.celery_client import app as celery_app

__all__ = ("celery_app",)
