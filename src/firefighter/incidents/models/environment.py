from __future__ import annotations

import uuid

from django.db import models
from django.db.models.manager import Manager


class Environment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=128, unique=True)
    description = models.CharField(max_length=128, unique=True)
    order = models.IntegerField(default=0)
    default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = Manager["Environment"]()

    def __str__(self) -> str:
        return self.value

    @classmethod
    def get_default(cls) -> Environment:
        return Environment.objects.get(default=True)
