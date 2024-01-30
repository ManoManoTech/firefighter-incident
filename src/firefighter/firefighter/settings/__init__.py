"""This module define all the settings for the FireFighter project.

!!! warning

    **It should NOT be imported directly from any other module.**

    To use the settings, import them through Django's [django.conf.settings](https://docs.djangoproject.com/en/4.2/topics/settings/#using-settings-in-python-code) object:
    ```python
    from django.conf import settings
    ```

"""

# ruff: noqa: E402, F403
# pylint: disable=wrong-import-position
# isort: off
from __future__ import annotations

import os

os.environ["DJANGO_SETTINGS_MODULE"] = "firefighter.firefighter.settings"


# Monkey-patching Django, so stubs will work for all generics,
# see: https://github.com/typeddjango/django-stubs
import django_stubs_ext

django_stubs_ext.monkeypatch()

# Allow mapping of settings to environment variables
from firefighter.firefighter.settings.settings_utils import config
from decouple import Csv

FF_ENV_VAR_MAPPING_LIST = config("FF_ENV_VAR_MAPPING", cast=Csv(), default="")
FF_ENV_VAR_MAPPING = {
    k: v for k, v in (x.split(":") for x in FF_ENV_VAR_MAPPING_LIST) if k and v
}
for k, v in FF_ENV_VAR_MAPPING.items():
    os.environ[k] = os.environ.get(v, "")

from firefighter.firefighter.settings.settings_builder import *

# Monkey-patching DRF, to allow generics on some classes
# We need to do this after importing settings, as DRF uses them at import time
from rest_framework import fields, generics, viewsets

django_stubs_ext.monkeypatch(
    extra_classes=(fields.Field, generics.GenericAPIView, viewsets.GenericViewSet)
)
# XXX(dugab): remove in Django50
from django.forms.renderers import BaseRenderer

BaseRenderer.form_template_name = "django/forms/div.html"
BaseRenderer.formset_template_name = "django/forms/formsets/div.html"
