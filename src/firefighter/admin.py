from __future__ import annotations

from django.conf import settings
from django.contrib import admin

APP_DISPLAY_NAME: str = settings.APP_DISPLAY_NAME

admin.site.site_header = f"{APP_DISPLAY_NAME} Back-Office"
admin.site.site_title = f"{APP_DISPLAY_NAME} BO"
admin.site.index_title = f"{APP_DISPLAY_NAME} BO"

admin_custom = admin
