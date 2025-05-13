from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)


def link_auth_user(user: User, claim: dict[str, str | list[str]]) -> None:
    # ruff: noqa: PLC0415

    # Check that roles are in the claim
    group_names = claim.get("roles")
    if group_names is None or not isinstance(group_names, list):
        return

    # Map permissions

    from django.contrib.auth.models import Group

    # Check special "back_office" group which enables the connection to the BO
    if "back_office" in group_names:
        group_names.remove("back_office")
        if not user.is_staff:
            user.is_staff = True
            user.save()

    # Reset all groups
    user.groups.clear()
    # Add all groups received by SSO
    for group_name in group_names:
        try:
            group = Group.objects.get(name=group_name)
            group.user_set.add(
                user
            )  # pyright: ignore[reportGeneralTypeIssues]
        except Group.DoesNotExist:
            logger.warning(
                "Group %s from SSO does not exist in the application Groups!",
                group_name,
            )
