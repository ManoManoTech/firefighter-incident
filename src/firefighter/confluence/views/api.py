from __future__ import annotations

from firefighter.api.views._base import ReadOnlyModelViewSet
from firefighter.confluence.models import Runbook
from firefighter.confluence.serializers import RunbookSerializer


class RunbookViewSet(ReadOnlyModelViewSet[Runbook]):
    queryset = Runbook.objects.all()
    serializer_class = RunbookSerializer
