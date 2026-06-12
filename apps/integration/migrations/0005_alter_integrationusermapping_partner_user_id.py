from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integration", "0004_alter_valuemapping_unique_to_target"),
    ]

    operations = [
        migrations.AlterField(
            model_name="integrationusermapping",
            name="partner_user_id",
            field=models.CharField(
                blank=True,
                max_length=100,
                null=True,
                help_text=(
                    "ERP's own user ID. Null until ERP confirms the record. "
                    "Filled in by RecruiterSyncService or ApplicantSyncService."
                ),
            ),
        ),
    ]
