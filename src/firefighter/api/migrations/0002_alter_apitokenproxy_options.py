# Generated by Django 4.2.3 on 2023-07-04 09:06

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="apitokenproxy",
            options={
                "default_permissions": [],
                "permissions": [
                    ("can_edit_any", "Can reassign token to any user"),
                    ("can_add_any", "Can add token to any user"),
                    ("can_view_any", "Can view token of all users"),
                    ("can_delete_any", "Can delete token of any user"),
                    ("can_add_own", "Can add own tokens"),
                    ("can_view_own", "Can view own tokens"),
                    ("can_delete_own", "Can delete own tokens"),
                ],
                "verbose_name": "API Token",
            },
        ),
    ]
