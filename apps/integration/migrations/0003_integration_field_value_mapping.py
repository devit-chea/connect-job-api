import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integration", "0002_integrationhandshake_redirect_uri_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="IntegrationFieldMapping",
            fields=[
                ("create_date", models.DateTimeField(auto_now_add=True, null=True)),
                ("write_date", models.DateTimeField(auto_now=True, null=True)),
                ("create_uid", models.IntegerField(blank=True, editable=False, null=True)),
                ("write_uid", models.IntegerField(blank=True, editable=False, null=True)),
                ("create_ucp_id", models.CharField(blank=True, editable=False, null=True)),
                ("write_ucp_id", models.CharField(blank=True, editable=False, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_field", models.CharField(max_length=100)),
                ("target_field", models.CharField(max_length=100)),
                ("mapping_type", models.CharField(
                    choices=[("free", "Free"), ("mapped", "Mapped")],
                    default="free",
                    max_length=20,
                )),
                ("default_value", models.CharField(blank=True, max_length=255, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("partner", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="field_mappings",
                    to="integration.integrationpartner",
                )),
            ],
            options={
                "db_table": "integrate_field_mapping",
            },
        ),
        migrations.AddConstraint(
            model_name="integrationfieldmapping",
            constraint=models.UniqueConstraint(
                fields=("partner", "source_field"),
                name="uq_integrate_field_mapping_partner_source",
            ),
        ),
        migrations.CreateModel(
            name="IntegrationValueMapping",
            fields=[
                ("create_date", models.DateTimeField(auto_now_add=True, null=True)),
                ("write_date", models.DateTimeField(auto_now=True, null=True)),
                ("create_uid", models.IntegerField(blank=True, editable=False, null=True)),
                ("write_uid", models.IntegerField(blank=True, editable=False, null=True)),
                ("create_ucp_id", models.CharField(blank=True, editable=False, null=True)),
                ("write_ucp_id", models.CharField(blank=True, editable=False, null=True)),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source_value", models.CharField(max_length=255)),
                ("target_value", models.CharField(max_length=255)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("field_mapping", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="value_mappings",
                    to="integration.integrationfieldmapping",
                )),
            ],
            options={
                "db_table": "integrate_value_mapping",
            },
        ),
        migrations.AddConstraint(
            model_name="integrationvaluemapping",
            constraint=models.UniqueConstraint(
                fields=("field_mapping", "source_value"),
                name="uq_integrate_value_mapping_field_source",
            ),
        ),
    ]
