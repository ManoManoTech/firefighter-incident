from __future__ import annotations

from api.serializers import PrioritySerializer
from api.views._base import ReadOnlyModelViewSet
from incidents.models.priority import Priority


class PriorityViewSet(ReadOnlyModelViewSet[Priority]):
    queryset = Priority.objects.all()
    serializer_class = PrioritySerializer
