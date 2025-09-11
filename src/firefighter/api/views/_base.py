from __future__ import annotations

from typing import Any, Generic, TypeVar

from django.db.models import Model
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import mixins, viewsets

T_co = TypeVar("T_co", bound=Model, covariant=True)


@extend_schema(
    parameters=[
        OpenApiParameter(
            name="fields",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Comma-separated list of fields to include in a CSV or TSV render. Nested objects are de-nested and accessible with a dot `.`",
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
        )
    ],
)
class AdvancedGenericViewSet(viewsets.GenericViewSet[T_co], Generic[T_co]):
    """Generic viewset with support for fields and labels parameters, to customize fields of CSV and TSV renderer."""

    fields: list[str] = []
    """List of attributes/properties to be rendered in CSV/TSV format.
    For nested objects, a dot is used a separator.

     E.g. `fields = ["id", "name", "component.name", "component.group.name"]`
    """

    labels: dict[str, str] = {}
    """
    Dict mapping attributes/properties to a more friendly string to be shown in the header row for CSV/TSV renders.

    E.g. `labels = {"slack_channel_name": "Slack Channel"}`
    """

    def get_renderer_context(self) -> dict[str, Any]:
        context = super().get_renderer_context()

        if self.request.GET.get("fields") == "__all__":
            context["header"] = None
        else:
            context["header"] = (
                self.request.GET["fields"].split(",")
                if "fields" in self.request.GET
                else self.fields
            )
        if self.request.GET.get("labels") == "__original__":
            context["labels"] = None
        else:
            context["labels"] = (
                "__hidden__"
                if self.request.GET.get("labels") == "__hidden__"
                else self.labels
            )
        return context


class ReadOnlyModelViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    AdvancedGenericViewSet[T_co],
    Generic[T_co],
):
    pass
