import django.db.models.deletion
from django.db import migrations, models


def backfill_user_company_profile(apps, schema_editor):
    """
    For every existing recruiter/admin mapping (local_user_id == profile_id),
    resolve and set the matching UserCompanyProfile within that mapping's
    company. Rows that don't resolve to a UserCompanyProfile are applicant
    mappings (applicants have no company membership) and are left untouched.
    """
    IntegrationUserMapping = apps.get_model("integration", "IntegrationUserMapping")
    UserCompanyProfile = apps.get_model("auth_oauth", "UserCompanyProfile")

    mappings = (
        IntegrationUserMapping.objects
        .filter(user_company_profile__isnull=True)
        .select_related("connection")
    )

    for mapping in mappings:
        company_id = mapping.connection.organization_id
        ucp = (
            UserCompanyProfile.objects
            .filter(company_id=company_id)
            .filter(models.Q(profile_id=mapping.local_user_id) | models.Q(user_id=mapping.local_user_id))
            .order_by("-create_date")
            .first()
        )
        if ucp is not None:
            mapping.user_company_profile = ucp
            mapping.save(update_fields=["user_company_profile"])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("auth_oauth", "0001_initial"),
        ("integration", "0008_integration_sync_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationusermapping",
            name="user_company_profile",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="integration_user_mappings",
                to="auth_oauth.usercompanyprofile",
            ),
        ),
        migrations.RunPython(backfill_user_company_profile, noop_reverse),
        migrations.AlterUniqueTogether(
            name="integrationusermapping",
            unique_together={("connection", "local_user_id"), ("connection", "user_company_profile")},
        ),
    ]
