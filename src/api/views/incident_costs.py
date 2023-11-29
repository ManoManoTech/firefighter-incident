from __future__ import annotations

from api.serializers import IncidentCostSerializer
from api.views._base import ReadOnlyModelViewSet
from incidents.models.incident_cost import IncidentCost


class IncidentCostViewSet(ReadOnlyModelViewSet[IncidentCost]):
    queryset = IncidentCost.objects.all().select_related("cost_type")
    serializer_class = IncidentCostSerializer
