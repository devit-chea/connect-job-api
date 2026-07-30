from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("activity_tracking_app", "0002_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="jobpostuserstatemodel",
            index=models.Index(
                fields=["job_post_id", "status"],
                name="jpus_post_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobpostuserstatemodel",
            index=models.Index(
                fields=["user_company_profile_id"],
                name="jpus_ucp_idx",
            ),
        ),
    ]
