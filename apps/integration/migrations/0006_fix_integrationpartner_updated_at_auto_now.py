from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integration", "0005_alter_integrationusermapping_partner_user_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="integrationpartner",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]
