from __future__ import annotations

from rest_framework import serializers

from confluence.models import Runbook


class RunbookSerializer(serializers.ModelSerializer[Runbook]):
    class Meta:
        model = Runbook
        fields = "__all__"
