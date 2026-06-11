from django.core.management.base import BaseCommand
from apps.auth_oauth.services.super_admin_setup_service import SuperAdminSetupService


class Command(BaseCommand):
    help = "Create or update the default super admin user"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            required=True,
            help="Username of the super admin",
        )
        parser.add_argument(
            "--email",
            type=str,
            required=True,
            help="Email of the super admin",
        )

    def handle(self, *args, **options):
        username = options["username"]
        email = options["email"]

        self.stdout.write(self.style.NOTICE(f"Processing super admin: {username} ({email})"))

        try:
            SuperAdminSetupService.create_or_update_super_admin(username, email)
            self.stdout.write(self.style.SUCCESS("Super admin created/updated successfully."))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f"Error: {exc}"))
            raise exc
