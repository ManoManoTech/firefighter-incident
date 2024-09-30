from __future__ import annotations

import logging
import uuid
from itertools import groupby
from typing import Any, ClassVar

from django.db import models
from django.db.utils import IntegrityError
from django.utils import timezone
from django_stubs_ext.db.models import TypedModelMeta

from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.user import User

logger = logging.getLogger(__name__)

STATUS_HELP_TEXT = """The current state of the Service. Valid statuses are:
<ul>
<li><code>active</code>: The service is enabled and has no open incidents. This is the only status a service can be created with.</li>
<li><code>warning</code>: The service is enabled and has one or more acknowledged incidents.</li>
<li><code>critical</code>: The service is enabled and has one or more triggered incidents.</li>
<li><code>maintenance</code>: The service is under maintenance, no new incidents will be triggered during maintenance mode.</li>
<li><code>disabled</code>: The service is disabled and will not have any new triggered incidents.</li>
</ul>"""


class PagerDutyService(models.Model):
    """A Service represents an entity you monitor (such as a web Service, email Service, or database Service.)
    It is a container for related Incidents that associates them with Escalation Policies.
    A Service is the focal point for Incident management; Services specify the configuration for the behavior of Incidents triggered on them.
    This behavior includes specifying urgency and performing automated actions based on time of day, Incident duration, and other factors.

    - [Read more about Services in the PagerDuty Knowledge Base.](https://support.pagerduty.com/hc/en-us/sections/200550800-Services)
    """

    objects: ClassVar[models.Manager[PagerDutyService]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    status = models.CharField(max_length=16, help_text=STATUS_HELP_TEXT)  # XXX enum
    summary = models.CharField(
        max_length=256,
        help_text="A short-form, PD server-generated string that provides succinct, important information about an object suitable for primary labeling of an entity in a client. In many cases, this will be identical to name, though it is not intended to be an identifier. ",
    )
    api_url = models.URLField(
        max_length=256,
        help_text="The API show URL at which the object is accessible. Corresponds to PagerDuty API field `self`",
    )
    web_url = models.URLField(
        max_length=256,
        help_text="A URL at which the entity is uniquely displayed in the Web app. Corresponds to PagerDuty API field `html_url`",
    )
    pagerduty_id = models.CharField(
        max_length=64,
        help_text="PagerDuty ID for the service.",
        unique=True,
        db_index=True,
    )
    # TODO Escalation policy should not be null after migrations
    escalation_policy = models.ForeignKey(
        "PagerDutyEscalationPolicy", on_delete=models.CASCADE, null=True
    )

    ignore = models.BooleanField(
        default=False,
        help_text="Ignore this service. Ignored services can't be triggered, and are hidden ins most places.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TypedModelMeta):
        verbose_name = "PagerDuty service"
        verbose_name_plural = "PagerDuty services"

    def __str__(self) -> str:
        return f"{self.summary} ({self.pagerduty_id})"

    def get_absolute_url(self) -> str:
        return self.web_url


class PagerDutyIncident(models.Model):
    """An Incident represents a problem or an issue that needs to be addressed and resolved.

    Incidents can be thought of as a problem or an issue within your Service that needs to be addressed and resolved, they are normalized and de-duplicated.

    Incidents can be triggered, acknowledged, or resolved, and are assigned to a User based on the Service's Escalation Policy.

    A triggered Incident prompts a Notification to be sent to the current On-Call User(s) as defined in the Escalation Policy used by the Service.

    Incidents are triggered through the Events API or are created by Integrations.

    - [Read more about Incidents in the PagerDuty Knowledge Base.](https://support.pagerduty.com/hc/en-us/articles/202829250-What-Is-an-Incident-)
    """

    objects: ClassVar[models.Manager[PagerDutyIncident]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(
        max_length=256,
        help_text="A succinct description of the nature, symptoms, cause, or effect of the incident.",
    )
    summary = models.CharField(
        max_length=256,
        help_text="A short-form, server-generated string that provides succinct, important information about an object suitable for primary labeling of an entity in a client. In many cases, this will be identical to name, though it is not intended to be an identifier.",
    )
    service = models.ForeignKey(PagerDutyService, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=16,
        help_text="The current status of the incident. Allowed values: triggered, acknowledged, resolved",
    )  # XXX enum
    urgency = models.CharField(
        max_length=8,
        help_text="The urgency of the incident. Allowed values: high, low",
    )
    details = models.CharField(
        max_length=4000,
        help_text="Additional incident details. Corresponds to PagerDuty API field `body.details`",
    )
    api_url = models.URLField(
        max_length=256,
        help_text="The API show URL at which the object is accessible. Corresponds to PagerDuty API field `self`",
    )
    web_url = models.URLField(
        max_length=256,
        help_text="A URL at which the entity is uniquely displayed in the Web app. Corresponds to PagerDuty API field `html_url`",
    )
    incident_key = models.CharField(
        max_length=128,
        help_text="A string which identifies the incident. Sending subsequent requests referencing the same service and with the same incident_key will result in those requests being rejected if an open incident matches that incident_key.",
        unique=True,
    )
    incident_number = models.IntegerField(
        help_text="The number of the incident. This is unique across your account."
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    incident = models.ForeignKey(
        Incident,
        on_delete=models.CASCADE,
        related_name="pagerduty_incident_set",
        null=True,
    )

    class Meta(TypedModelMeta):
        verbose_name = "PagerDuty incident"
        verbose_name_plural = "PagerDuty incidents"

    def __str__(self) -> str:
        return f"{self.summary} ({self.incident_key})"

    def get_absolute_url(self) -> str:
        return self.web_url


class PagerDutyUserManager(models.Manager["PagerDutyUser"]):
    def get_or_none(self, **kwargs: Any) -> PagerDutyUser | None:
        try:
            return self.get(**kwargs)
        except PagerDutyUser.DoesNotExist:
            return None

    @staticmethod
    def upsert_by_pagerduty_id(
        pagerduty_id: str,
        email: str,
        phone_number: str,
        name: str,
    ) -> User | None:
        """Returns a User from PagerDuty info.
        It will update a PagerDutyUser and its associated User if the name, phone, PagerDuty team changes.
        """
        # Get a user by its email and update the name. Create the user if necessary.
        ff_user, _ = User.objects.update_or_create(email=email, defaults={"name": name})

        # Update or create a PD User, with the key being its user. Update other fields.
        try:
            pd_user, _ = PagerDutyUser.objects.update_or_create(
                user=ff_user,
                defaults={
                    "pagerduty_id": pagerduty_id,
                    "phone_number": phone_number,
                },
            )

            if pd_user.user == ff_user:
                return ff_user
            logger.warning(
                "PD and FF users not matching. PDID=%s, email=%s",
                pagerduty_id,
                email,
            )

        except IntegrityError:
            logger.warning(
                "IntegrityError! Could not upsert PagerDuty User. PDID=%s, email=%s.",
                pagerduty_id,
                email,
                exc_info=True,
            )

            pd_user, _ = PagerDutyUser.objects.update_or_create(
                pagerduty_id=pagerduty_id,
                defaults={
                    "user": ff_user,
                    "phone_number": phone_number,
                },
            )
            return ff_user
        return None

    @staticmethod
    def get_current_on_call_users_l1() -> list[User]:
        """Returns the list of oncall first responders in each escalation policy. Only the lowest escalation level user is returned per Escalation Policy.

        These users have their PagerDutyUser associated.
        """
        ep_user = PagerDutyOncall.objects.get_current_oncalls_per_escalation_policy()
        users: list[User] = [oncall[1][0].pagerduty_user.user for oncall in ep_user]

        return users


class PagerDutyTeam(models.Model):

    objects: ClassVar[models.Manager[PagerDutyTeam]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True)
    description = models.CharField(max_length=1024, null=True, blank=True)
    pagerduty_id = models.CharField(max_length=128, unique=True, db_index=True)
    pagerduty_api_url = models.URLField(max_length=256, null=True, blank=True)
    pagerduty_url = models.URLField(max_length=256, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(TypedModelMeta):
        verbose_name = "PagerDuty team"
        verbose_name_plural = "PagerDuty teams"

    def __str__(self) -> str:
        return self.name


class PagerDutyUser(models.Model):
    objects: PagerDutyUserManager = PagerDutyUserManager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="pagerduty_user"
    )
    name = models.CharField(max_length=256, null=True, blank=True)
    pagerduty_id = models.CharField(max_length=128, unique=True, db_index=True)
    pagerduty_api_url = models.URLField(max_length=256, null=True, blank=True)
    pagerduty_url = models.URLField(max_length=256, null=True, blank=True)
    phone_number = models.CharField(max_length=128, blank=True, default="")
    teams = models.ManyToManyField[PagerDutyTeam, PagerDutyTeam](
        PagerDutyTeam, related_name="pagerduty_user_set", blank=True
    )

    class Meta(TypedModelMeta):
        verbose_name = "PagerDuty user"
        verbose_name_plural = "PagerDuty users"

    def __str__(self) -> str:
        return self.pagerduty_id


class PagerDutyEscalationPolicy(models.Model):
    """An Escalation Policy determines what User or Schedule will be Notified and in what order. This will happen when an Incident is triggered.

    Escalation Policies can be used by one or more Services.

    *Escalation Rules*

    - An Escalation Policy is made up of multiple Escalation Rules. Each Escalation Rule represents a level of On-Call duty.
    - It specifies one or more Users or Schedules to be notified when an unacknowledged Incident reaches that Escalation Rule.
    - The first Escalation Rule in the Escalation Policy is the User that will be notified about the triggered Incident.
    - If all On-Call User for a given Escalation Rule have been acknowledged of an Incident and the Escalation Rule's escalation delay has elapsed, the Incident escalates to the next Escalation Rule.

    - [Read more about Escalation Policies in the PagerDuty Knowledge Base](https://support.pagerduty.com/hc/en-us/articles/202828950-What-is-an-escalation-policy-)
    - [API Schema](https://developer.pagerduty.com/api-reference/c2NoOjI3NDgwMjE-escalation-policy)
    """

    objects: ClassVar[models.Manager[PagerDutyEscalationPolicy]]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pagerduty_id = models.CharField(max_length=128, unique=True, db_index=True)

    name = models.CharField(max_length=128, unique=True)
    summary = models.CharField(max_length=128, null=True, blank=True)
    description = models.CharField(max_length=1024, null=True, blank=True)

    pagerduty_api_url = models.URLField(max_length=256, null=True, blank=True)
    pagerduty_url = models.URLField(max_length=256, null=True, blank=True)

    teams = models.ManyToManyField(
        PagerDutyTeam, related_name="pagerduty_escalation_policy_set", blank=True
    )

    class Meta(TypedModelMeta):
        verbose_name_plural = "PagerDuty escalation policies"
        verbose_name = "PagerDuty escalation policy"

    def __str__(self) -> str:
        return f"{self.name} ({self.pagerduty_id})"


class PagerDutySchedule(models.Model):
    """A Schedule determines the time periods that Users are On-Call.

    Only On-Call Users are eligible to receive Notifications from firefighter.incidents.

    The details of the On-Call Schedule specify which single User is On-Call for that Schedule at any given point in time.

    An On-Call Schedule consists of one or more Schedule Layers that rotate a group of Users through the same shift at a set interval.

    Schedules are used by Escalation Policies as an escalation target for a given Escalation Rule.

    - [Read more about On-Call Schedules in the PagerDuty Knowledge Base](https://support.pagerduty.com/hc/en-us/sections/200550790-On-Call-Schedules)
    - [API Schema](https://developer.pagerduty.com/api-reference/c2NoOjI3NDgwMzU-schedule)
    """

    objects: ClassVar[models.Manager[PagerDutySchedule]]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pagerduty_id = models.CharField(max_length=128, unique=True, db_index=True)

    summary = models.CharField(max_length=128, null=True, blank=True)

    pagerduty_api_url = models.URLField(max_length=256, null=True, blank=True)
    pagerduty_url = models.URLField(max_length=256, null=True, blank=True)
    # TODO: Add more fields

    escalation_policies = models.ManyToManyField(
        PagerDutyEscalationPolicy, related_name="pagerduty_schedule_set", blank=True
    )
    users = models.ManyToManyField(
        PagerDutyUser, related_name="pagerduty_schedule_set", blank=True
    )
    teams = models.ManyToManyField(
        PagerDutyTeam, related_name="pagerduty_schedule_set", blank=True
    )

    class Meta(TypedModelMeta):
        verbose_name = "PagerDuty schedule"
        verbose_name_plural = "PagerDuty schedules"

    def __str__(self) -> str:
        return f"{self.summary} ({self.pagerduty_id})"


class PagerDutyOncallManager(models.Manager["PagerDutyOncall"]):
    def get_current_oncalls_per_escalation_policy(
        self,
    ) -> list[tuple[PagerDutyEscalationPolicy, list[PagerDutyOncall]]]:
        """Returns the list of on call Users. These users have their PagerDutyUser associated."""
        oncalls = (
            self.select_related(
                "pagerduty_user",
                "schedule",
                "escalation_policy",
                "pagerduty_user",
                "pagerduty_user__user__slack_user",
            )
            .filter(
                models.Q(start__lte=timezone.now(), end__gte=timezone.now())
                | models.Q(end__isnull=True)
            )
            .exclude(escalation_policy__pagerdutyservice__ignore__exact=True)
            .order_by("escalation_level")
            .order_by(
                "escalation_policy__pagerdutyservice",
                "pagerduty_user",
            )
            .distinct("escalation_policy__pagerdutyservice", "pagerduty_user")
        )
        oncalls_grouped: list[
            tuple[PagerDutyEscalationPolicy, list[PagerDutyOncall]]
        ] = []
        for escalation_policy, oncalls_grouper in groupby(
            oncalls, key=lambda x: x.escalation_policy
        ):
            oncalls_list = sorted(oncalls_grouper, key=lambda x: x.escalation_level)
            oncalls_grouped.append((escalation_policy, oncalls_list))
        return oncalls_grouped

    def get_current_oncalls_per_escalation_policy_name_first_responder(
        self,
    ) -> dict[str, User]:
        res = self.get_current_oncalls_per_escalation_policy()
        # Get only the first
        return {
            ep.name: oncalls[0].pagerduty_user.user
            for ep, oncalls in res
            if len(oncalls) > 0
        }


class PagerDutyOncall(models.Model):
    """An On-Call represents a contiguous unit of time for which a User will be On-Call for a given Escalation Policy and Escalation Rule.

    This may be the result of that User always being On-Call for the Escalation Rule, or a block of time during which the computed result of a Schedule on that Escalation Rule puts the User On-Call.

    During an On-Call, the User is expected to bear responsibility for responding to any Notifications they receive and working to resolve the associated Incident(s).

    On-Calls cannot be created directly through the API; they are the computed result of how Escalation Policies and Schedules are configured. The API provides read-only access to the On-Calls generated by PagerDuty.

    - [Read more about On-Call Schedules in the PagerDuty Knowledge Base](https://support.pagerduty.com/hc/en-us/sections/200550790-On-Call-Schedules)
    - [API Schema](https://developer.pagerduty.com/api-reference/c2NoOjI3NDgwNDc-oncall)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    escalation_policy = models.ForeignKey(
        PagerDutyEscalationPolicy, on_delete=models.CASCADE, related_name="oncall_set"
    )
    pagerduty_user = models.ForeignKey(
        PagerDutyUser, on_delete=models.CASCADE, related_name="oncall_set"
    )
    schedule = models.ForeignKey(
        PagerDutySchedule,
        on_delete=models.CASCADE,
        related_name="oncall_set",
        null=True,
        blank=True,
    )
    escalation_level = models.IntegerField(
        help_text="The escalation level for the on-call."
    )
    start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The start of the on-call. If null, the on-call is a permanent user on-call.",
    )
    end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="The end of the on-call. If null, the user does not go off-call.",
    )

    objects = PagerDutyOncallManager()

    class Meta(TypedModelMeta):
        verbose_name = "PagerDuty on-call"
        verbose_name_plural = "PagerDuty on-calls"

    def __str__(self) -> str:
        return f"{self.pagerduty_user} ({self.escalation_policy}) - {self.start} to {self.end}"

    @property
    def user_name(self) -> str | None:
        return self.pagerduty_user.name
