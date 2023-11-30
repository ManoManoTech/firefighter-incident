from __future__ import annotations

from firefighter.api.serializers import GroupSerializer
from firefighter.api.views._base import ReadOnlyModelViewSet
from firefighter.incidents.models.group import Group


class GroupViewSet(ReadOnlyModelViewSet[Group]):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
