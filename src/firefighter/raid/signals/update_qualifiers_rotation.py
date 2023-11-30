from __future__ import annotations

import datetime
from typing import Any

from django.conf import settings
from django.db.models import Max
from django.db.models.signals import post_delete, post_save
from django.dispatch.dispatcher import receiver

from firefighter.jira_app.models import JiraUser
from firefighter.raid.models import Qualifier, QualifierRotation

RAID_DEFAULT_JIRA_QRAFT_USER_ID: str = settings.RAID_DEFAULT_JIRA_QRAFT_USER_ID


def complete_qualifiers_rotation() -> None:
    qualifiers_rotation_last_date = last_date_to_maintain(only_protected=False)
    adding_twice_rotation(qualifiers_rotation_last_date)


def adding_twice_rotation(next_day_to_add: datetime.date) -> None:
    qualifiers_queryset = (
        Qualifier.objects.select_related("jira_user")
        .filter(jira_user__user__is_active=True)
        .order_by("id")
    )
    # Adding twice the rotation
    for jira_user in list(qualifiers_queryset) * 2:
        next_day_to_add = next_day_to_add + datetime.timedelta(days=1)
        # We avoid weekends
        if next_day_to_add.weekday() == 5:
            next_day_to_add = next_day_to_add + datetime.timedelta(days=2)
        # Updating the rotation
        QualifierRotation.objects.update_or_create(
            day=next_day_to_add,
            defaults={
                "jira_user": jira_user.jira_user,
                "protected": False,
            },
        )


def last_date_to_maintain(*, only_protected: bool) -> datetime.date:
    base_queryset = (
        QualifierRotation.objects.filter(
            day__gte=datetime.datetime.now(tz=datetime.UTC).date(),
        )
        .order_by("day")
        .select_related("day")
    )
    if only_protected:
        base_queryset = base_queryset.filter(protected=True)
    qualifiers_rotation_last_date = base_queryset.aggregate(Max("day")).get("day__max")
    if qualifiers_rotation_last_date is None:
        qualifiers_rotation_last_date = datetime.datetime.now(tz=datetime.UTC).date()
    return qualifiers_rotation_last_date


@receiver(signal=post_save, sender=Qualifier)
def new_qualifier(sender: Any, instance: Any, created: int, **kwargs: Any) -> None:
    if created == 1:
        qualifiers_rotation_last_date_protected = last_date_to_maintain(
            only_protected=True
        )
        QualifierRotation.objects.filter(
            day__gte=qualifiers_rotation_last_date_protected
            + datetime.timedelta(days=1),
        ).delete()
        adding_twice_rotation(qualifiers_rotation_last_date_protected)


@receiver(signal=post_delete, sender=Qualifier)
def deleted_qualifier(sender: Any, instance: Qualifier, **kwargs: Any) -> None:
    qualifiers_rotation_last_date_protected = last_date_to_maintain(only_protected=True)
    qualifier_rotation_dates_to_use_default_value = (
        QualifierRotation.objects.filter(
            day__gte=datetime.datetime.now(tz=datetime.UTC).date(),
            day__lte=qualifiers_rotation_last_date_protected,
        )
        .order_by("day")
        .filter(jira_user=instance.jira_user)
    )
    # Replacing with default qualifier for dates assigned to the deleted qualifier before last protected date
    for day in qualifier_rotation_dates_to_use_default_value:
        QualifierRotation.objects.update_or_create(
            day=day.day,
            defaults={
                "jira_user": JiraUser.objects.get(id=RAID_DEFAULT_JIRA_QRAFT_USER_ID),
            },
        )
    # Deleting rotation after last protected date
    QualifierRotation.objects.filter(
        day__gte=qualifiers_rotation_last_date_protected + datetime.timedelta(days=1),
    ).delete()
    # Adding new rotation after last protected date
    adding_twice_rotation(qualifiers_rotation_last_date_protected)
