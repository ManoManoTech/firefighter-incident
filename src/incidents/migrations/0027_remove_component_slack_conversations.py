# Generated by Django 4.1.2 on 2022-10-27 15:45

from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0026_alter_user_options"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="component",
            name="slack_conversations",
        ),
    ]
