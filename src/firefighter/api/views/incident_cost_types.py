from __future__ import annotations

from firefighter.api.serializers import IncidentCostTypeSerializer
from firefighter.api.views._base import ReadOnlyModelViewSet
from firefighter.incidents.models.incident_cost_type import IncidentCostType


class IncidentCostTypeViewSet(ReadOnlyModelViewSet[IncidentCostType]):
    queryset = IncidentCostType.objects.all()
    serializer_class = IncidentCostTypeSerializer
