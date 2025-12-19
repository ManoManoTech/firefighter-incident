"""Django management command to backdate an incident's mitigated_at timestamp for testing."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from firefighter.incidents.models.incident import Incident


class Command(BaseCommand):
    """Backdate an incident's mitigated_at timestamp for testing post-mortem reminders."""

    help = "Backdate an incident's mitigated_at timestamp by a specified number of days"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "incident_id",
            type=int,
            help="ID of the incident to backdate",
        )
        parser.add_argument(
            "--days",
            type=int,
            default=6,
            help="Number of days to backdate (default: 6, to trigger 5-day reminder)",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Reset mitigated_at to current time instead of backdating",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        incident_id = options["incident_id"]
        days = options["days"]
        reset = options["reset"]

        try:
            incident = Incident.objects.get(id=incident_id)
        except Incident.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Incident #{incident_id} does not exist")
            )
            return

        if reset:
            incident.mitigated_at = timezone.now()
            incident.save(update_fields=["mitigated_at"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Reset mitigated_at for incident #{incident_id} to current time: {incident.mitigated_at}"
                )
            )
        else:
            old_value = incident.mitigated_at
            new_value = timezone.now() - timedelta(days=days)
            incident.mitigated_at = new_value
            incident.save(update_fields=["mitigated_at"])

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Backdated incident #{incident_id} mitigated_at:"
                )
            )
            self.stdout.write(f"   Old value: {old_value}")
            self.stdout.write(f"   New value: {new_value}")
            self.stdout.write(f"   Backdated by {days} days")

        self.stdout.write("\nIncident details:")
        self.stdout.write(f"   ID: {incident.id}")
        self.stdout.write(f"   Title: {incident.title}")
        self.stdout.write(f"   Priority: {incident.priority.name}")
        self.stdout.write(f"   Status: {incident.status.label}")
        self.stdout.write(f"   Needs postmortem: {incident.needs_postmortem}")
        self.stdout.write(f"   Mitigated at: {incident.mitigated_at}")

        if incident.needs_postmortem and days >= 5:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  This incident should now trigger a 5-day reminder!"
                )
            )
            self.stdout.write(
                "\nTo test the reminder, run:"
            )
            self.stdout.write(
                self.style.NOTICE(
                    "   pdm run python manage.py test_postmortem_reminders"
                )
            )
