from __future__ import annotations

from api.serializers import IncidentCostTypeSerializer
from api.views._base import ReadOnlyModelViewSet
from incidents.models.incident_cost_type import IncidentCostType


class IncidentCostTypeViewSet(ReadOnlyModelViewSet[IncidentCostType]):
    queryset = IncidentCostType.objects.all()
    serializer_class = IncidentCostTypeSerializer
