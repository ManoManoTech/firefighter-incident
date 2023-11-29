from __future__ import annotations

from api.views._base import ReadOnlyModelViewSet
from confluence.models import Runbook
from confluence.serializers import RunbookSerializer


class RunbookViewSet(ReadOnlyModelViewSet[Runbook]):
    queryset = Runbook.objects.all()
    serializer_class = RunbookSerializer
