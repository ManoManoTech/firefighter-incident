from __future__ import annotations

from firefighter.api.serializers import IncidentCostSerializer
from firefighter.api.views._base import ReadOnlyModelViewSet
from firefighter.incidents.models.incident_cost import IncidentCost


class IncidentCostViewSet(ReadOnlyModelViewSet[IncidentCost]):
    queryset = IncidentCost.objects.all().select_related("cost_type")
    serializer_class = IncidentCostSerializer
