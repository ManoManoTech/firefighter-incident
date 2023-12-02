from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from firefighter.confluence.tasks import sync_runbooks


class Command(BaseCommand):
    help = "Sync runbooks from Confluence. This is a wrapper for the [firefighter.confluence.tasks.sync_runbooks][] task."

    def handle(self, *args: Any, **options: Any) -> Any:
        return sync_runbooks()
