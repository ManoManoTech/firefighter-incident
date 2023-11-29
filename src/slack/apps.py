from __future__ import annotations

from django.apps import AppConfig

from slack.signals import incident_channel_done


class SlackConfig(AppConfig):
    name = "slack"

    def ready(self) -> None:
        # Register the Signals once all models from all apps have been loaded
        from slack.signals import (
            create_incident_conversation,
            get_users,
            handle_incident_channel_done,
            incident_closed,
            incident_updated,
            postmortem_created,
            roles_reminders,
        )
        from slack.tasks import send_message
