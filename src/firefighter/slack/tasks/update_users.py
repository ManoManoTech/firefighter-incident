from __future__ import annotations

import logging
from typing import Any

from celery import shared_task

from firefighter.slack.models import SlackUser

logger = logging.getLogger(__name__)


@shared_task(
    name="slack.update_users_from_slack",
    retry_kwargs={"max_retries": 2},
    default_retry_delay=90,
)
def update_users_from_slack(*_args: Any, **_options: Any) -> None:
    """Retrieves users from Slack and updates the database (e.g. name, new profile picture, email, active status...)."""
    queryset = SlackUser.objects.all().order_by("user__updated_at")[:100]
    for slack_user in queryset:
        slack_user.update_user_info()
