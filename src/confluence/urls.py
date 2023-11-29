from __future__ import annotations

from django.apps import apps
from django.urls import path
from rest_framework import routers

from api.urls import urlpatterns as api_urlspatterns
from confluence.apps import ConfluenceConfig
from confluence.views.api import RunbookViewSet
from confluence.views.runbook.runbook_list import RunbooksViewList

app_name = ConfluenceConfig.name
urlpatterns = [
    path("runbook/", RunbooksViewList.as_view(), name="runbook_list"),
]


# Patch `api` app router, if installed
if apps.is_installed("api"):
    router = routers.DefaultRouter()
    router.include_root_view = False
    router.register(r"runbooks", RunbookViewSet, basename="runbooks")
    api_urlspatterns.extend(router.urls)
