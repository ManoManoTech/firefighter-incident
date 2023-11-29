from __future__ import annotations

from api.serializers import ComponentSerializer
from api.views._base import ReadOnlyModelViewSet
from incidents.models.component import Component


class ComponentViewSet(ReadOnlyModelViewSet[Component]):
    queryset = Component.objects.all().select_related("group")
    serializer_class = ComponentSerializer
