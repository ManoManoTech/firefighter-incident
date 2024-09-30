# Generated by Django 4.2.11 on 2024-04-30 15:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("incidents", "0001_initial_oss"),
    ]

    operations = [
        migrations.AlterField(
            model_name="severity",
            name="name",
            field=models.CharField(max_length=128, unique=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="password",
            field=models.CharField(max_length=128, verbose_name="password"),
        ),
        migrations.CreateModel(
            name="FeatureTeam",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=80)),
                ("jira_project_key", models.CharField(max_length=10, unique=True)),
            ],
            options={
                "unique_together": {("name", "jira_project_key")},
                "verbose_name": "Feature Team",
                "verbose_name_plural": "Feature Teams",
            },
        ),
    ]