# Generated manually on 2025-08-19 - Remove RaidArea model

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("raid", "0002_featureteam_remove_qualifierrotation_jira_user_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="RaidArea",
        ),
    ]
