from __future__ import annotations

from firefighter.api.serializers import PrioritySerializer
from firefighter.api.views._base import ReadOnlyModelViewSet
from firefighter.incidents.models.priority import Priority


class PriorityViewSet(ReadOnlyModelViewSet[Priority]):
    queryset = Priority.objects.all()
    serializer_class = PrioritySerializer
