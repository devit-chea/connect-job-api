from django.db import migrations

# RecruiterAdminCreateRecruiterView has zero row-level scope restriction today
# (full company visibility). The new record_scope column defaults to "own" for
# safety on future/unconfigured rows, but applying that default to EXISTING
# admin_recruiter_manage_user grants would silently lock every admin_recruiter
# down to nothing the moment this migration runs. Backfill existing rows to
# "all" so today's behavior is preserved; only new/edited grants start "own".
TARGET_CODENAME = "admin_recruiter_manage_user"


def backfill_to_all(apps, schema_editor):
    RolePermission = apps.get_model("auth_oauth", "RolePermission")
    RolePermission.objects.filter(permission__codename=TARGET_CODENAME).update(
        record_scope="all"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("auth_oauth", "0008_rolepermission_record_scope"),
    ]

    operations = [
        migrations.RunPython(backfill_to_all, reverse_code=migrations.RunPython.noop),
    ]
