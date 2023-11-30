from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from firefighter.confluence.tasks import sync_postmortems


class Command(BaseCommand):
    help = "Sync Confluence PostMortems and save them in DB. THis is a wrapper around the Celery task."
    requires_migrations_checks = False
    requires_system_checks: list[Any] = []

    def handle(self, *args: Any, **options: Any) -> None:
        sync_postmortems()
