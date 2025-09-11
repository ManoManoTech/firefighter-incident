from __future__ import annotations

import logging
from typing import Any

from django.apps import apps
from django.db.models.query import Prefetch

from firefighter.firefighter.views import CustomDetailView
from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)
SELECT_RELATED = []
if apps.is_installed("firefighter.slack"):
    SELECT_RELATED.append("slack_user")
    from firefighter.slack.models import Conversation, UserGroup
if apps.is_installed("firefighter.pagerduty"):
    SELECT_RELATED.append("pagerduty_user")


class UserDetailView(CustomDetailView[User]):
    """In this view, be extra careful.

    In this context, `user` is the logged_in user and `target_user` is the user of the profile being viewed.
    """

    template_name = "pages/user_detail.html"
    context_object_name: str = "target_user"
    pk_url_kwarg = "user_id"
    model = User
    select_related = SELECT_RELATED
    queryset = User.objects.select_related(*select_related).prefetch_related(
        Prefetch(
            "conversation_set",
            queryset=Conversation.objects.not_incident_channel()
            .exclude(tag="")
            .filter(incident_categories__isnull=False)
            .distinct()
            .prefetch_related(Prefetch("members")),
        ),
        Prefetch(
            "usergroup_set",
            queryset=UserGroup.objects.filter(incident_categories__isnull=False)
            .distinct()
            .prefetch_related(Prefetch("members")),
        ),
    )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        target_user: User = context[self.context_object_name]

        additional_context = {
            "page_title": f"{target_user.full_name} | User",
        }

        return {**context, **additional_context}
