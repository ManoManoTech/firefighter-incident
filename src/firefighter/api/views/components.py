from __future__ import annotations

from firefighter.api.serializers import IncidentCategorySerializer
from firefighter.api.views._base import ReadOnlyModelViewSet
from firefighter.incidents.models.incident_category import IncidentCategory


class IncidentCategoryViewSet(ReadOnlyModelViewSet[IncidentCategory]):
    queryset = IncidentCategory.objects.all().select_related("group")
    serializer_class = IncidentCategorySerializer
