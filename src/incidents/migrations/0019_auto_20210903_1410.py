# Generated by Django 3.2.6 on 2021-09-03 12:10

from __future__ import annotations

import taggit.managers
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("taggit", "0003_taggeditem_add_unique_index"),
        ("incidents", "0018_alter_incidentupdate__status"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="tags",
            field=taggit.managers.TaggableManager(
                blank=True,
                help_text="A comma-separated list of tags.",
                through="taggit.TaggedItem",
                to="taggit.Tag",
                verbose_name="Tags",
            ),
        )
    ]
