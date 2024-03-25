"""WSGI config for firefighter project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/wsgi/
"""

from __future__ import annotations

# We need to be able to shadow virtualenv things with our own code
# So we reverse the order of the last two parts of the load path
import os

# Load the WSGI Application (as we should do)


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "firefighter.firefighter.settings")
# pylint: disable=wrong-import-position
# noinspection PyPep8
from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
