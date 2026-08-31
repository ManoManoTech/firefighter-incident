"""Django management command to test the incident process reminders."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q
from django.utils import timezone

from firefighter.firefighter.filters import readable_time_delta
from firefighter.incidents.enums import IncidentStatus
from firefighter.incidents.models.incident import Incident
from firefighter.slack.tasks.send_postmortem_reminders import (
    send_postmortem_reminders,
)


class Command(BaseCommand):
    """Test the process reminders by executing the task manually."""

    help = "Execute the incident process reminder task manually for testing"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--list-only",
            action="store_true",
            help="Only list eligible incidents without sending reminders",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        list_only = options["list_only"]

        self.stdout.write(self.style.MIGRATE_HEADING("Process Reminder Testing"))
        self.stdout.write("=" * 70)

        first_delay = timedelta(seconds=settings.FF_PROCESS_REMINDER_FIRST_DELAY)
        repeat_seconds = settings.FF_PROCESS_REMINDER_REPEAT_DELAY
        cutoff_date = timezone.now() - first_delay

        self.stdout.write(
            f"\n⏰ First reminder after: {readable_time_delta(first_delay)} "
            f"(FF_PROCESS_REMINDER_FIRST_DELAY={settings.FF_PROCESS_REMINDER_FIRST_DELAY}s)"
        )
        if repeat_seconds > 0:
            self.stdout.write(
                f"🔁 Then repeated every: {readable_time_delta(timedelta(seconds=repeat_seconds))} "
                f"of inactivity (FF_PROCESS_REMINDER_REPEAT_DELAY={repeat_seconds}s)"
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"🔁 Repeats disabled (FF_PROCESS_REMINDER_REPEAT_DELAY={repeat_seconds})"
                )
            )
        self.stdout.write(f"📅 Cutoff date: {cutoff_date}")
        self.stdout.write(f"🕐 Current time: {timezone.now()}\n")

        # Same scope as the task itself
        eligible_incidents = (
            Incident.objects.filter(
                Q(priority__value__lte=3) | Q(priority__needs_postmortem=True),
                mitigated_at__lte=cutoff_date,
                mitigated_at__isnull=False,
                _status__in=[
                    IncidentStatus.MITIGATED.value,
                    IncidentStatus.POST_MORTEM.value,
                ],
                ignore=False,
            )
            .select_related("priority", "environment", "conversation")
            .prefetch_related("roles_set__role_type", "roles_set__user__slack_user")
        )

        count = eligible_incidents.count()
        self.stdout.write(f"🔍 Found {count} incident(s) in scope\n")

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
            self.stdout.write("\nOr, to rehearse the flow in minutes:")
            self.stdout.write(
                self.style.NOTICE(
                    "   FF_PROCESS_REMINDER_FIRST_DELAY=60 FF_PROCESS_REMINDER_REPEAT_DELAY=120 \\\n"
                    "     pdm run python manage.py backdate_incident_mitigated <incident_id> --minutes 5"
                )
            )
            return

        # Display eligible incidents
        for incident in eligible_incidents:
            commander = incident.commander
            mitigated_for = (
                readable_time_delta(timezone.now() - incident.mitigated_at)
                if incident.mitigated_at
                else "unknown"
            )

            self.stdout.write(f"  📋 Incident #{incident.id}")
            self.stdout.write(f"     Title: {incident.title}")
            self.stdout.write(f"     Priority: {incident.priority.name}")
            self.stdout.write(f"     Status: {incident.status.label}")
            self.stdout.write(f"     Mitigated: {incident.mitigated_at}")
            self.stdout.write(f"     Mitigated for: {mitigated_for}")
            self.stdout.write(f"     Needs post-mortem: {incident.needs_postmortem}")
            self.stdout.write(
                f"     Commander: {commander.user if commander else '∅ (unassigned)'}"
            )
            self.stdout.write(f"     Environment: {incident.environment.value}")
            self.stdout.write(f"     Private: {incident.private}")
            self.stdout.write("")

        if list_only:
            self.stdout.write(self.style.SUCCESS("✅ List-only mode: No reminders sent"))
            self.stdout.write("\nTo send reminders, run without --list-only flag")
            return

        # Execute the task
        self.stdout.write("=" * 70)
        self.stdout.write(self.style.WARNING("🚀 Executing process reminder task...\n"))

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
