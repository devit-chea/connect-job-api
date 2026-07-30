from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_oauth", "0004_user_phone_number_user_telegram_chat_id_and_more"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["email"], name="user_email_idx"),
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["status", "is_active"], name="user_status_active_idx"),
        ),
    ]
