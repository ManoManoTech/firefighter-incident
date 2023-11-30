from __future__ import annotations

from firefighter.api.serializers import EnvironmentSerializer
from firefighter.api.views._base import ReadOnlyModelViewSet
from firefighter.incidents.models.environment import Environment


class EnvironmentViewSet(ReadOnlyModelViewSet[Environment]):
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer
