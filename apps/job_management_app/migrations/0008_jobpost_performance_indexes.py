from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("job_management_app", "0007_merge_20260601_1658"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="jobpostmodel",
            index=models.Index(
                fields=["company_id", "is_deleted", "status"],
                name="jp_company_deleted_status_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobpostmodel",
            index=models.Index(
                fields=["company_id", "create_ucp_id"],
                name="jp_company_ucp_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobpostmodel",
            index=models.Index(fields=["expire_date"], name="jp_expire_date_idx"),
        ),
        migrations.AddIndex(
            model_name="jobpostmodel",
            index=models.Index(fields=["create_date"], name="jp_create_date_idx"),
        ),
        migrations.AddIndex(
            model_name="jobapplicationmodel",
            index=models.Index(fields=["profile_id"], name="ja_profile_idx"),
        ),
        migrations.AddIndex(
            model_name="jobapplicationmodel",
            index=models.Index(
                fields=["job_post_id", "is_deleted"],
                name="ja_job_deleted_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="jobapplicationmodel",
            index=models.Index(fields=["apply_date"], name="ja_apply_date_idx"),
        ),
    ]
