from __future__ import annotations

from importlib import import_module

# pylint: disable=wildcard-import
# isort: off
from firefighter.firefighter.settings.settings_utils import SETTINGS_ENV, config
from firefighter.firefighter.settings.components.api import *
from firefighter.firefighter.settings.components.caches import *
from firefighter.firefighter.settings.components.celery import *
from firefighter.firefighter.settings.components.common import *
from firefighter.firefighter.settings.components.confluence import *
from firefighter.firefighter.settings.components.jira_app import *
from firefighter.firefighter.settings.components.logging import *
from firefighter.firefighter.settings.components.pagerduty import *
from firefighter.firefighter.settings.components.slack import *
from firefighter.firefighter.settings.components.raid import *

# Load dev or prod settings:
if SETTINGS_ENV == "dev":
    from firefighter.firefighter.settings.environments.dev import *
elif SETTINGS_ENV == "prod":
    from firefighter.firefighter.settings.environments.prod import *
else:
    err_msg = f"Unknown environment: {SETTINGS_ENV}"
    raise ValueError(err_msg)


FF_ADDITIONAL_SETTINGS_MODULE = config("FF_ADDITIONAL_SETTINGS_MODULE", default=None)

if FF_ADDITIONAL_SETTINGS_MODULE:
    try:
        m = import_module(FF_ADDITIONAL_SETTINGS_MODULE)
        # Set locals from the module
        for item in dir(m):
            if not item.startswith("__"):
                globals()[item] = getattr(m, item)

    except ImportError as exc:
        msg = f"Couldn't import {FF_ADDITIONAL_SETTINGS_MODULE}. Are you sure it's installed and available on your PYTHONPATH environment variable? Did you forget to activate a virtual environment?"
        raise ImportError(msg) from exc
