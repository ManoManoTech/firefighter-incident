from __future__ import annotations

from api.serializers import GroupSerializer
from api.views._base import ReadOnlyModelViewSet
from incidents.models.group import Group


class GroupViewSet(ReadOnlyModelViewSet[Group]):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
