from django.db import migrations

# Hardcode the literal codes rather than importing
# apps.auth_oauth.constants.auth_constants.DefaultRole — migrations should not
# depend on application code that can change independently of migration history.
DEFAULT_ROLE_CODES = [
    "OPERATOR_DEFAULT_ROLE",
    "ADMIN_RECRUITER_ROLE",
    "RECRUITER_ROLE",
    "APPLICANT_ROLE",
    "PENDING_ADMIN_RECRUITER_DEFAULT_ROLE",
]


def set_is_default_true(apps, schema_editor):
    Role = apps.get_model("auth_oauth", "Role")
    Role.objects.filter(code__in=DEFAULT_ROLE_CODES).update(is_default=True)


def unset_is_default(apps, schema_editor):
    Role = apps.get_model("auth_oauth", "Role")
    Role.objects.filter(code__in=DEFAULT_ROLE_CODES).update(is_default=False)


class Migration(migrations.Migration):

    dependencies = [
        ("auth_oauth", "0006_role_custom_for_ucp"),
    ]

    operations = [
        migrations.RunPython(set_is_default_true, reverse_code=unset_is_default),
    ]
