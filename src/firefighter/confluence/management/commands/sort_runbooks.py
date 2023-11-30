from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from firefighter.confluence.tasks.sort_runbooks import sort_runbooks

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Sort runbooks."
    requires_migrations_checks = False
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--dry-run", dest="dry_run", action="store_true")
        parser.set_defaults(dry_run=False)

    def handle(self, *args: Any, **options: Any) -> Any:
        return sort_runbooks(dry_run=options["dry_run"])
