from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import EmailValidator
from django.db.models import Model, QuerySet
from drf_spectacular.extensions import (
    OpenApiSerializerExtension,
)
from rest_framework import serializers
from rest_framework.fields import empty
from taggit.serializers import TaggitSerializer, TagListSerializerField

from firefighter.firefighter.utils import get_in
from firefighter.incidents.models.environment import Environment
from firefighter.incidents.models.group import Group
from firefighter.incidents.models.incident import Incident
from firefighter.incidents.models.incident_category import IncidentCategory
from firefighter.incidents.models.incident_cost import IncidentCost
from firefighter.incidents.models.incident_cost_type import IncidentCostType
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.metric_type import IncidentMetric, MetricType
from firefighter.incidents.models.priority import Priority
from firefighter.incidents.models.user import User

if TYPE_CHECKING:
    from collections.abc import Callable, MutableMapping, Sequence

    from drf_spectacular.openapi import AutoSchema
    from drf_spectacular.utils import Direction


logger = logging.getLogger(__name__)

T = TypeVar("T", bound=Model)


class GroupedModelSerializer(serializers.RelatedField[T, Any, Any], Generic[T]):
    """Generic implementation for a model with a One2Many, where instead of a list we want the items grouped by a field, like costs or metrics."""

    def __init__(
        self,
        child_serializer: type[serializers.ModelSerializer[T]],
        key_getter: Callable[[T], str] = lambda x: str(x.pk),
        **kwargs: Any,
    ):
        self.child_serializer = child_serializer
        self.key_getter = key_getter
        if not kwargs.get("read_only", True):
            raise ValueError("GroupedModelSerializer can only be read_only")
        if "read_only" not in kwargs:
            kwargs["read_only"] = True
        kwargs["many"] = True
        super().__init__(**kwargs)

    def to_representation(self, value: Sequence[T]) -> dict[str, Any]:  # type: ignore[override]
        return {
            self.key_getter(child): self.child_serializer(child).data for child in value
        }


class GroupedModelSerializerOpenAPI(OpenApiSerializerExtension):  # type: ignore[no-untyped-call]
    target_class = "api.serializers.GroupedModelSerializer"
    target: GroupedModelSerializer[Any]

    def map_serializer(
        self, auto_schema: AutoSchema, direction: Direction
    ) -> dict[str, Any]:
        child_schema = auto_schema.resolve_serializer(
            self.target.child_serializer, direction
        )
        child_schema_ref = child_schema.ref or child_schema
        return {"type": "object", "additionalProperties": child_schema_ref}

    def get_name(
        self,
        auto_schema: AutoSchema,  # noqa: ARG002
        direction: Direction,  # noqa: ARG002
    ) -> str:
        return f"GroupedModelSerializer_{self.target.child_serializer.__name__}"


class CreatableSlugRelatedField(serializers.SlugRelatedField[T], Generic[T]):
    """Like [SlugRelatedField](https://www.django-rest-framework.org/api-guide/relations/#slugrelatedfield), but allows to create an object that is not present in DB."""

    def to_internal_value(self, data: str | None) -> T:
        if self.slug_field is None:
            raise ValueError(
                "SlugRelatedField requires the `slug_field` attribute to be set."
            )

        try:
            data_get_or_create: MutableMapping[str, Any] = {self.slug_field: data}
        except ObjectDoesNotExist:
            logger.warning("Object does not exist. Creating...")
            # XXX Improve behaviour when user does not exist
            self.get_queryset().create(**{self.slug_field: data})
        except (TypeError, ValueError):
            return self.fail("invalid")
        else:
            queryset: QuerySet[T] = self.get_queryset()
            return queryset.get(**data_get_or_create)
        return self.fail("invalid")

    def run_validation(self, data: Any = empty) -> T | Any | None:
        """Override the default validation to perform the validation before trying to create the object."""
        (is_empty_value, data) = self.validate_empty_values(data)
        if is_empty_value:
            return data
        self.run_validators(data)
        return self.to_internal_value(data)


class DurationFieldSeconds(serializers.DurationField):
    def to_representation(self, value: timedelta) -> float:  # type: ignore[override]
        return value.total_seconds()

    def to_internal_value(self, value: float) -> timedelta:  # type: ignore[override]
        return timedelta(seconds=value)


class EnvironmentSerializer(serializers.ModelSerializer[Environment]):
    class Meta:
        model = Environment
        exclude = ["created_at", "updated_at"]


class IncidentRoleSerializer(serializers.ModelSerializer[IncidentRole]):
    class Meta:
        model = IncidentRole
        fields = "__all__"


class IncidentRoleInlineSerializer(IncidentRoleSerializer):
    name = serializers.StringRelatedField[User](read_only=True, source="user.name")
    email = serializers.StringRelatedField[User](read_only=True, source="user.email")
    id = serializers.PrimaryKeyRelatedField[User](read_only=True, source="user.id")

    class Meta:
        model = IncidentRole
        fields = ["id", "name", "email"]


class PrioritySerializer(serializers.ModelSerializer[Priority]):
    class Meta:
        depth = 1
        model = Priority
        fields = "__all__"


class GroupSerializer(serializers.ModelSerializer[Group]):
    class Meta:
        model = Group
        fields = "__all__"


class IncidentCategorySerializer(serializers.ModelSerializer[IncidentCategory]):
    group = GroupSerializer()

    class Meta:
        model = IncidentCategory
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["id", "name", "email"]


class IncidentCostTypeSerializer(serializers.ModelSerializer[IncidentCostType]):
    class Meta:
        model = IncidentCostType
        fields = "__all__"


class IncidentCostSerializer(serializers.ModelSerializer[IncidentCost]):
    cost_type = IncidentCostTypeSerializer()

    class Meta:
        model = IncidentCost
        fields = "__all__"


class IncidentCostSerializerInline(IncidentCostSerializer):
    class Meta:
        model = IncidentCost
        fields = ["amount", "details"]


class IncidentMetricSerializer(serializers.ModelSerializer[IncidentMetric]):
    duration = serializers.DurationField(read_only=True)
    duration_seconds = DurationFieldSeconds(read_only=True, source="duration")
    metric_type = serializers.StringRelatedField[MetricType](read_only=True)

    class Meta:
        model = IncidentMetric
        exclude = ["id", "incident"]


class IncidentSerializer(TaggitSerializer, serializers.ModelSerializer[Incident]):
    environment = EnvironmentSerializer(read_only=True)
    environment_id = serializers.PrimaryKeyRelatedField(
        source="environment", queryset=Environment.objects.all(), write_only=True
    )
    priority = PrioritySerializer(read_only=True)
    priority_id = serializers.PrimaryKeyRelatedField(
        source="priority", queryset=Priority.objects.all(), write_only=True
    )
    incident_category = IncidentCategorySerializer(read_only=True)
    incident_category_id = serializers.PrimaryKeyRelatedField(
        source="incident_category", queryset=IncidentCategory.objects.all(), write_only=True
    )

    status = serializers.SerializerMethodField()
    created_by = UserSerializer(read_only=True)
    slack_channel_name = serializers.SerializerMethodField()
    postmortem_url = serializers.SerializerMethodField()

    created_by_email = CreatableSlugRelatedField[User](
        source="created_by",
        write_only=True,
        slug_field="email",
        queryset=User.objects.all(),
        validators=[EmailValidator()],  # type: ignore[list-item]
    )

    tags = TagListSerializerField(read_only=True)
    metrics = GroupedModelSerializer(
        source="metrics_prefetched",
        child_serializer=IncidentMetricSerializer,
        key_getter=lambda x: x.metric_type.type,
    )
    costs = GroupedModelSerializer[IncidentCost](
        source="costs_prefetched",
        child_serializer=IncidentCostSerializerInline,
        key_getter=lambda x: x.cost_type.name,
    )
    roles = GroupedModelSerializer[IncidentRole](
        source="roles_prefetched",
        child_serializer=IncidentRoleInlineSerializer,
        key_getter=lambda x: str(x.role_type.slug),
    )

    @staticmethod
    def get_status(obj: Incident) -> str:
        return obj.status.label

    @staticmethod
    def get_slack_channel_name(obj: Incident) -> str:
        return f"#{obj.slack_channel_name}" if obj.slack_channel_name else ""

    @staticmethod
    def get_postmortem_url(obj: Incident) -> str | None:
        """Return the Confluence post-mortem page URL if it exists."""
        if hasattr(obj, "postmortem_for"):
            return obj.postmortem_for.page_url
        return None

    def create(self, validated_data: dict[str, Any]) -> Incident:
        return Incident.objects.declare(**validated_data)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        remove_fields = get_in(kwargs, "context.remove_fields", [])
        super().__init__(*args, **kwargs)

        if remove_fields:
            # for multiple fields in a list
            for field_name in remove_fields:
                self.fields.pop(field_name)

    class Meta:
        model = Incident
        depth = 2
        fields = [
            "id",
            "title",
            "status",
            "description",
            "created_at",
            "environment",
            "incident_category",
            "priority",
            "status",
            "slack_channel_name",
            "status_page_url",
            "postmortem_url",
            "status",
            "environment_id",
            "incident_category_id",
            "priority_id",
            "created_by_email",
            "tags",
            "created_by",
            "costs",
            "metrics",
            "roles",
            "ignore",
        ]
