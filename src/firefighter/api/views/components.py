from __future__ import annotations

from firefighter.api.serializers import ComponentSerializer
from firefighter.api.views._base import ReadOnlyModelViewSet
from firefighter.incidents.models.component import Component


class ComponentViewSet(ReadOnlyModelViewSet[Component]):
    queryset = Component.objects.all().select_related("group")
    serializer_class = ComponentSerializer
