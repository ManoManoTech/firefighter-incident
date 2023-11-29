from __future__ import annotations

from api.serializers import EnvironmentSerializer
from api.views._base import ReadOnlyModelViewSet
from incidents.models.environment import Environment


class EnvironmentViewSet(ReadOnlyModelViewSet[Environment]):
    queryset = Environment.objects.all()
    serializer_class = EnvironmentSerializer
