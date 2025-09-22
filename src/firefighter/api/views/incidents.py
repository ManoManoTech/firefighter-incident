from __future__ import annotations

from typing import TYPE_CHECKING, Never

from django.db.models import Prefetch, QuerySet
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response

from firefighter.api.serializers import IncidentSerializer
from firefighter.api.views._base import AdvancedGenericViewSet
from firefighter.incidents.models.incident import Incident, IncidentFilterSet
from firefighter.incidents.models.incident_cost import IncidentCost
from firefighter.incidents.models.incident_membership import IncidentRole
from firefighter.incidents.models.metric_type import IncidentMetric
from firefighter.incidents.signals import create_incident_conversation

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.serializers import BaseSerializer


class ProcessAfterResponse(Response):
    """Custom DRF Response, to trigger the Slack workflow after creating the incident and returning HTTP 201."""

    def close(self) -> None:
        super().close()
        incident = Incident.objects.get(id=self.data["id"])
        create_incident_conversation.send(
            "api",
            incident=incident,
        )


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="fields",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Comma-separated list of fields to include in a CSV or TSV render. Nested objects are de-nested and accessible with a dot `.`. Non-existent fields will generate empty rows.",
            default="__all__",
            examples=[
                OpenApiExample(
                    name="Comma separated list of fields",
                    value="id,name,incident_category.name,incident_category.group.name",
                    request_only=True,
                ),
                OpenApiExample(
                    name="All fields (default)",
                    value="__all__",
                    request_only=True,
                ),
            ],
        ),
        OpenApiParameter(
            name="show_tags",
            type=bool,
            location=OpenApiParameter.QUERY,
            description="Whether to include tags in the output.",
            default=False,
            examples=[OpenApiExample(name="Show tags", value=True, request_only=True)],
        ),
    ],
)
class IncidentViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    AdvancedGenericViewSet[Incident],
):
    queryset = (
        Incident.objects.all()
        .select_related(
            "priority",
            "incident_category__group",
            "incident_category",
            "environment",
            "conversation",
            "created_by",
        )
        .prefetch_related(
            Prefetch(
                "metric_set",
                queryset=IncidentMetric.objects.all()
                .order_by("id")
                .select_related("metric_type"),
                to_attr="metrics_prefetched",
            ),
            Prefetch(
                "incident_cost_set",
                queryset=IncidentCost.objects.all()
                .order_by("id")
                .select_related("cost_type"),
                to_attr="costs_prefetched",
            ),
            Prefetch(
                "roles_set",
                queryset=IncidentRole.objects.all()
                .order_by("id")
                .select_related("role_type", "user"),
                to_attr="roles_prefetched",
            ),
        )
    )
    serializer_class = IncidentSerializer
    serializer_context = {"remove_fields": ["tags"]}
    filterset_class = IncidentFilterSet
    fields = [
        "id",
        "status",
        "environment.value",
        "priority.name",
        "title",
        "description",
        "incident_category.name",
        "incident_category.group.name",
        "created_at",
        "slack_channel_name",
        "status_page_url",
        "metrics.*.duration_seconds",
        "costs.*.amount",
        "roles.*.email",
    ]

    def list(self, request: Request, *args: Never, **kwargs: Never) -> Response:
        """List all incidents. Allows to show or hide tags which is DB intensive, with the show_tags parameters.

        `status` and `_status__*` uses an enum:
        ```
        10, "Open"
        20, "Investigating"
        30, "Mitigating"
        40, "Mitigated"
        50, "Post-mortem"
        60, "Closed"
        ```
        """
        queryset = self.filter_queryset(self.get_queryset())
        serializer: BaseSerializer[Incident]
        if request.query_params.get("show_tags") == "true":
            serializer = IncidentSerializer(
                queryset, many=True, context={"remove_fields": []}
            )
        else:
            serializer = self.get_serializer(
                queryset, many=True, context={"remove_fields": ["tags"]}
            )
        return Response(serializer.data)


@extend_schema(
    examples=[
        OpenApiExample(
            "Create an incident",
            summary="Create an incident",
            description="Create an incident, on INT, P4, with `Other` incident category and John Doe as creator. All fields are required. The email must be a valid email of a ManoMano employee, that has a Slack account or has already used FireFighter before.",
            value={
                "title": "Title of the incident, limited to 128 characters.",
                "description": "Longer description of the incident. No characters limit.",
                "environment_id": "1b960430-995b-47e1-beab-23dbe3dbccbf",
                "incident_category_id": "390a993a-d273-4db8-b7d6-190ab294961a",
                "priority_id": "b814c9d2-48a8-4ac4-9c71-ff844e1b77f1",
                "created_by_email": "john.doe@mycompany.com",
            },
            request_only=True,  # signal that example only applies to requests
            response_only=False,  # signal that example only applies to responses
        ),
        OpenApiExample(
            "Create incident response",
            status_codes=["201"],
            summary="Create incident response",
            description="Successfully created incident. Notice that the Slack channel is not created yet. You can retrieve the Slack channel by making a GET call after a few seconds.",
            value={
                "id": 886,
                "title": "Title of the incident, limited to 128 characters.",
                "status": "Open",
                "description": "Longer description of the incident. No characters limit.",
                "created_at": "2022-02-18T12:16:10.960407+01:00",
                "environment": {
                    "id": "1b960430-995b-47e1-beab-23dbe3dbccbf",
                    "value": "INT",
                    "name": "Int",
                    "description": "Integration environment",
                    "order": 3,
                    "default": False,
                },
                "incident_category": {
                    "id": "390a993a-d273-4db8-b7d6-190ab294961a",
                    "name": "Other",
                    "description": "",
                    "order": 200,
                    "created_at": "2019-12-13T15:44:53+01:00",
                    "updated_at": "2021-07-30T15:28:52.692000+02:00",
                    "group": {
                        "id": "13a1b0b2-9ff9-4c2b-b665-f497102459d7",
                        "name": "Other",
                        "description": "",
                        "order": 100000,
                        "created_at": "2020-04-14T18:12:42+02:00",
                        "updated_at": "2021-08-02T11:57:09.306000+02:00",
                    },
                },
                "priority": {
                    "id": "b814c9d2-48a8-4ac4-9c71-ff844e1b77f1",
                    "name": "P4",
                    "value": 4,
                    "emoji": "🌦️",
                    "description": "Minor issue not affecting customers.",
                    "order": 3,
                    "default": True,
                    "needs_postmortem": False,
                    "created_at": "2021-02-19T17:54:03.586000+01:00",
                    "updated_at": "2021-06-25T18:00:28.819000+02:00",
                },
                "slack_channel_name": "#None",
                "status_page_url": "https://incidents.mycompany.com/incident/1234",
                "tags": [],
                "metrics": [],
                "costs": [],
                "created_by": {
                    "name": "John Doe",
                    "email": "john.doe@mycompany.com",
                },
                "commander": {
                    "name": "John Doe",
                    "email": "john.doe@mycompany.com",
                },
                "communication_lead": {
                    "name": "John Doe",
                    "email": "john.doe@mycompany.com",
                },
            },
            request_only=False,
            response_only=True,
        ),
    ]
)
class CreateIncidentViewSet(
    mixins.CreateModelMixin,
    viewsets.GenericViewSet[Incident],
):
    queryset: QuerySet[Incident] = Incident.objects.all().select_related(
        "priority", "incident_category__group", "incident_category", "environment", "conversation"
    )
    serializer_class = IncidentSerializer
    filterset_class = IncidentFilterSet
    renderer_classes = [JSONRenderer]

    def create(self, request: Request, *args: Never, **kwargs: Never) -> Response:
        """Allow to create an incident.
        Requires a valid Bearer token, that you can create in the back-office if you have the right permissions.
        """
        serializer: BaseSerializer[Incident] = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return ProcessAfterResponse(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def perform_create(self, serializer: BaseSerializer[Incident]) -> None:
        serializer.save()
