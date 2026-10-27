"""Django management command to load the initial list of partners."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from firefighter.incidents.models.partner import Partner


class Command(BaseCommand):
    """Create the given partners, reviewed and active. Idempotent: existing ones are kept."""

    help = (
        "Create partners (third-party providers an incident can come from). "
        'Example: create_partners Algolia Cloudflare "Microsoft Azure (OpenAI)"'
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("names", nargs="+", help="Partner names")

    def handle(self, *args: Any, **options: Any) -> None:
        for name in options["names"]:
            partner, created = Partner.objects.get_or_create_by_name(name)
            if created:
                # Loaded by an administrator: no need for a review
                partner.is_reviewed = True
                partner.save(update_fields=["is_reviewed", "updated_at"])
                self.stdout.write(self.style.SUCCESS(f"Created {partner.name}"))
            else:
                self.stdout.write(f"Already exists: {partner.name}")
