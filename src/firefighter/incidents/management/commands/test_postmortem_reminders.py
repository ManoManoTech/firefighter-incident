"""Django management command to test post-mortem reminders."""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.utils import timezone

from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.slack.tasks.send_postmortem_reminders import (
    POSTMORTEM_REMINDER_DAYS,
    send_postmortem_reminders,
)


class Command(BaseCommand):
    """Test post-mortem reminders by executing the task manually."""

    help = "Execute the post-mortem reminder task manually for testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--list-only",
            action="store_true",
            help="Only list eligible incidents without sending reminders",
        )

    def handle(self, *args, **options):
        list_only = options["list_only"]

        self.stdout.write(self.style.MIGRATE_HEADING("Post-Mortem Reminder Testing"))
        self.stdout.write("=" * 70)

        # Calculate cutoff date
        cutoff_date = timezone.now() - timezone.timedelta(days=POSTMORTEM_REMINDER_DAYS)

        self.stdout.write(f"\n⏰ Reminder threshold: {POSTMORTEM_REMINDER_DAYS} days")
        self.stdout.write(f"📅 Cutoff date: {cutoff_date}")
        self.stdout.write(f"🕐 Current time: {timezone.now()}\n")

        # Find eligible incidents
        eligible_incidents = Incident.objects.filter(
            mitigated_at__lte=cutoff_date,
            mitigated_at__isnull=False,
            _status__gte=IncidentStatus.MITIGATED.value,
            _status__lt=IncidentStatus.CLOSED.value,
            priority__needs_postmortem=True,
            ignore=False,
        ).select_related("priority", "environment", "conversation")

        count = eligible_incidents.count()
        self.stdout.write(f"🔍 Found {count} incident(s) eligible for reminder\n")

        if count == 0:
            self.stdout.write(
                self.style.WARNING("⚠️  No incidents found needing reminders")
            )
            self.stdout.write("\nTo test, you can backdate an incident with:")
            self.stdout.write(
                self.style.NOTICE(
                    "   pdm run python manage.py backdate_incident_mitigated <incident_id> --days 6"
                )
            )
            return

        # Display eligible incidents
        for incident in eligible_incidents:
            days_since_mitigated = (
                timezone.now() - incident.mitigated_at
            ).days if incident.mitigated_at else 0

            self.stdout.write(f"  📋 Incident #{incident.id}")
            self.stdout.write(f"     Title: {incident.title}")
            self.stdout.write(f"     Priority: {incident.priority.name}")
            self.stdout.write(f"     Status: {incident.status.label}")
            self.stdout.write(f"     Mitigated: {incident.mitigated_at}")
            self.stdout.write(
                f"     Days since mitigated: {days_since_mitigated} days"
            )
            self.stdout.write(f"     Environment: {incident.environment.value}")
            self.stdout.write(f"     Private: {incident.private}")
            self.stdout.write("")

        if list_only:
            self.stdout.write(
                self.style.SUCCESS(
                    "✅ List-only mode: No reminders sent"
                )
            )
            self.stdout.write("\nTo send reminders, run without --list-only flag")
            return

        # Execute the task
        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.WARNING("🚀 Executing post-mortem reminder task...\n")
        )

        try:
            send_postmortem_reminders()
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(
                self.style.SUCCESS("✅ Task execution completed successfully!")
            )
        except Exception as e:
            self.stdout.write("\n" + "=" * 70)
            self.stdout.write(self.style.ERROR(f"❌ Task execution failed: {e}"))
            raise
