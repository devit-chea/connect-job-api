from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integration", "0006_fix_integrationpartner_updated_at_auto_now"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationpartner",
            name="erp_domain",
            field=models.URLField(
                blank=True,
                max_length=500,
                null=True,
                help_text="Base URL of the Connect ERP instance (from company.integrate_domain).",
            ),
        ),
    ]
