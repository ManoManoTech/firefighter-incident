from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0033_create_jira_webhook_service_user"),
    ]

    operations = [
        migrations.AddField(
            model_name="incident",
            name="dedup_key",
            field=models.CharField(
                blank=True,
                null=True,
                max_length=160,
                help_text=(
                    "Idempotency key for automated sources (e.g. Datadog->IMPACT). "
                    "While the incident is open (status <= Mitigated), no two incidents "
                    "may share a dedup_key. Left empty (NULL) for manually-created "
                    "incidents, which are never de-duplicated."
                ),
            ),
        ),
        migrations.AddConstraint(
            model_name="incident",
            # At most one *open* incident (status <= 40 == Mitigated) per dedup_key.
            # Partial unique index: NULL keys never collide, and once an incident
            # reaches Post-mortem/Closed it leaves the index, freeing the key for a
            # future recurrence.
            constraint=models.UniqueConstraint(
                fields=("dedup_key",),
                condition=models.Q(("dedup_key__isnull", False), ("_status__lte", 40)),
                name="incidents_incident__unique_open_dedup_key",
            ),
        ),
    ]
