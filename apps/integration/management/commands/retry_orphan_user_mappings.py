import logging

from django.core.management.base import BaseCommand

from apps.integration.constants import ConnectorStatus
from apps.integration.models.job_platform import IntegrationUserMapping

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Re-queue ERP sync for IntegrationUserMapping rows whose partner_user_id "
        "is NULL (ERP never confirmed the record). Only retries mappings that "
        "belong to an active integration partner."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print orphans without dispatching Celery tasks.",
        )

    def handle(self, *args, **options):
        from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
        from apps.integration.tasks import sync_recruiter_to_erp

        dry_run = options["dry_run"]

        orphans = (
            IntegrationUserMapping.objects
            .select_related("connection", "user_company_profile")
            .filter(
                partner_user_id__isnull=True,
                connection__status=ConnectorStatus.ACTIVE,
            )
        )

        total = orphans.count()
        self.stdout.write(f"Found {total} orphaned mapping(s).")

        queued = 0
        skipped = 0

        for mapping in orphans:
            local_id = mapping.local_user_id

            # Prefer the direct FK — unambiguous, no guessing needed. Only
            # fall back to matching by profile/user id for legacy rows written
            # before user_company_profile existed.
            ucp = mapping.user_company_profile
            if ucp is None:
                company_id = mapping.connection.organization_id

                ucp = (
                    UserCompanyProfile.objects
                    .filter(company_id=company_id)
                    .filter(
                        models_q_profile_or_user(local_id)
                    )
                    .select_related("user", "profile", "company")
                    .first()
                )

            if ucp is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  SKIP  local_user_id={local_id} — no matching UserCompanyProfile "
                        f"(may be an applicant mapping; re-sync not supported here)"
                    )
                )
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  DRY   local_user_id={local_id} ucp_id={ucp.id} → would queue sync_recruiter_to_erp"
                )
            else:
                sync_recruiter_to_erp.delay(ucp.id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  QUEUE local_user_id={local_id} ucp_id={ucp.id} → sync_recruiter_to_erp queued"
                    )
                )
            queued += 1

        self.stdout.write(
            f"\nDone. queued={queued} skipped={skipped} total={total}"
            + (" (dry-run, no tasks dispatched)" if dry_run else "")
        )


def models_q_profile_or_user(local_id):
    from django.db.models import Q
    return Q(profile_id=local_id) | Q(user_id=local_id)
