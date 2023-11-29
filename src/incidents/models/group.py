from __future__ import annotations

import uuid

from django.db import models
from django.db.models.manager import Manager


class Group(models.Model):
    objects = Manager["Group"]()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name
