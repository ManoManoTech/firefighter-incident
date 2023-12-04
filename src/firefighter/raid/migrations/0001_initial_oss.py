# Generated by Django 4.2.7 on 2023-12-04 10:46

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    replaces = [
        ("raid", "0001_initial_squashed_0008_qualifierrotation"),
        ("raid", "0009_alter_jiraticket_business_impact"),
        ("raid", "0010_raidarea"),
        ("raid", "0010_jiraticket_issue_type_jiraticket_project_key"),
        ("raid", "0011_merge_20230408_1956"),
        ("raid", "0012_jiraticketimpact_jiraticket_impacts"),
        ("raid", "0013_alter_jiraticket_watchers"),
        ("raid", "0014_alter_jiraticket_business_impact"),
        ("raid", "0015_alter_jiraticket_assignee_alter_jiraticket_reporter_and_more"),
        ("raid", "0016_remove_jiraticket_assignee_and_more"),
        ("raid", "0017_alter_qualifierrotation_options_and_more"),
        ("raid", "0018_alter_qualifier_jira_user_and_more"),
    ]

    dependencies = [
        ("jira_app", "0005_alter_jiraissue_assignee"),
        ("incidents", "0036_severity_enabled_create_severity_enabled_update_and_more"),
        (
            "incidents",
            "0039_impact_impacttype_incidentimpact_impact_impact_type_and_more",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("jira_app", "0001_initial"),
        ("jira_app", "0003_jiraissue"),
    ]
    operations = [
        migrations.CreateModel(
            name="JiraTicket",
            fields=[
                (
                    "jiraissue_ptr",
                    models.OneToOneField(
                        auto_created=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        parent_link=True,
                        primary_key=True,
                        serialize=False,
                        to="jira_app.jiraissue",
                    ),
                ),
                (
                    "business_impact",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="It maps with customfield_10936",
                        max_length=128,
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Jira ticket",
                "verbose_name_plural": "Jira tickets",
            },
            bases=("jira_app.jiraissue",),
        ),
        migrations.CreateModel(
            name="RaidArea",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=128)),
                (
                    "area",
                    models.CharField(
                        choices=[
                            ("Sellers", "Sellers"),
                            ("Internal", "Internal"),
                            ("Customers", "Customers"),
                        ],
                        max_length=32,
                    ),
                ),
            ],
            options={
                "unique_together": {("name", "area")},
            },
        ),
        migrations.CreateModel(
            name="QualifierRotation",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("day", models.DateField(unique=True)),
                (
                    "protected",
                    models.BooleanField(
                        default=False,
                        help_text="If checked, it is because this rotation was previously modified so this date won't be deleted and it can not be unprotected again from here.",
                    ),
                ),
                (
                    "jira_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="jira_app.jirauser",
                    ),
                ),
            ],
            options={
                "verbose_name": "Qualifiers rotation",
                "verbose_name_plural": "Qualifiers rotation",
            },
        ),
        migrations.CreateModel(
            name="Qualifier",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "jira_user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="jira_app.jirauser",
                    ),
                ),
            ],
            options={
                "verbose_name": "Qualifier",
                "verbose_name_plural": "Qualifiers",
            },
        ),
        migrations.CreateModel(
            name="JiraTicketImpact",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "impact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="incidents.impact",
                    ),
                ),
                (
                    "jira_ticket",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="raid.jiraticket",
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="jiraticket",
            name="impacts",
            field=models.ManyToManyField(
                through="raid.JiraTicketImpact", to="incidents.impact"
            ),
        ),
        migrations.AddField(
            model_name="jiraticket",
            name="incident",
            field=models.OneToOneField(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="jira_ticket",
                to="incidents.incident",
            ),
        ),
    ]
