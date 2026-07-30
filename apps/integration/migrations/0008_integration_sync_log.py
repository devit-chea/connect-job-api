import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integration", "0007_integrationpartner_erp_domain"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationSyncLog",
            fields=[
                ("create_date", models.DateTimeField(auto_now_add=True, blank=True, null=True)),
                ("write_date", models.DateTimeField(auto_now=True, blank=True, null=True)),
                ("create_uid", models.IntegerField(blank=True, editable=False, null=True)),
                ("write_uid", models.IntegerField(blank=True, editable=False, null=True)),
                ("create_ucp_id", models.CharField(blank=True, editable=False, null=True)),
                ("write_ucp_id", models.CharField(blank=True, editable=False, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "partner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_logs",
                        to="integration.integrationpartner",
                    ),
                ),
                (
                    "sync_type",
                    models.CharField(
                        choices=[
                            ("job_post_inbound", "Inbound Job Post"),
                            ("pipeline_outbound", "Outbound Pipeline Sync"),
                            ("applicant_outbound", "Outbound Applicant Sync"),
                            ("pipeline_inbound", "Inbound Pipeline Update"),
                        ],
                        db_index=True,
                        max_length=30,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("failed", "Failed"),
                            ("retrying", "Retrying"),
                            ("success", "Success"),
                        ],
                        db_index=True,
                        default="failed",
                        max_length=20,
                    ),
                ),
                ("reference_id", models.CharField(blank=True, db_index=True, max_length=255, null=True)),
                ("payload", models.JSONField(default=dict)),
                ("error_message", models.TextField(blank=True, default="")),
                ("retry_count", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("last_attempted_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "integration_sync_log",
                "ordering": ["-created_at"],
            },
        ),
    ]
