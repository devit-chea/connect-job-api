from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.base.utils.file_management_util import FileURLService


class ApplicantInvitationService:

    @staticmethod
    def get_invitations_by_step(
        *, job_application_id: int, pipeline_step_id: int, pipeline_config_id: int
    ) -> list:
        invs = list(
            Invitation.objects.filter(
                job_application_id=job_application_id,
                pipeline_step_id=pipeline_step_id,
                pipeline_config_id=pipeline_config_id,
            )
            .select_related("mail_template")
            .order_by("-create_date")
        )

        step_map = {inv.id: inv for inv in invs}
        referenced_ids = {
            inv.rescheduled_from_id
            for inv in invs
            if inv.rescheduled_from_id is not None
        }

        entries = []
        visited_ids = set()

        for inv in invs:
            if inv.id in visited_ids:
                continue

            if inv.rescheduled_from_id is not None:
                main = step_map.get(inv.rescheduled_from_id)
                if main and main.id not in visited_ids:
                    entries.append({"main": main, "sub": inv})
                    visited_ids.add(inv.id)
                    visited_ids.add(main.id)
            elif inv.id not in referenced_ids:
                entries.append({"main": inv, "sub": None})
                visited_ids.add(inv.id)

        # Sort by main.id ASC
        entries = sorted(entries, key=lambda x: x["main"].id)

        return entries

    @staticmethod
    def get_invitation_entry_by_id(
        *, invitation_id: int, job_application_id: int, company
    ) -> dict | None:
        try:
            main = Invitation.objects.select_related("mail_template").get(
                id=invitation_id,
                job_application_id=job_application_id,
                company=company,
            )
        except Invitation.DoesNotExist:
            return None

        # Collect full reschedule chain from this main
        all_related = list(
            Invitation.objects.filter(
                job_application_id=job_application_id,
                pipeline_step_id=main.pipeline_step_id,
                pipeline_config_id=main.pipeline_config_id,
            )
            .select_related("mail_template")
            .order_by("-create_date")
        )

        def collect_subs(root_id, invs):
            subs = []
            children = sorted(
                [inv for inv in invs if inv.rescheduled_from_id == root_id],
                key=lambda x: x.create_date,
                reverse=True,
            )
            for child in children:
                subs.append(child)
                subs.extend(collect_subs(child.id, invs))
            return subs

        subs = collect_subs(main.id, all_related)
        return {"main": main, "subs": subs}

    @staticmethod
    def build_recruiter_map(invitations: list) -> dict:
        ucp_ids = {
            int(inv.create_ucp_id)
            for inv in invitations
            if inv.create_ucp_id is not None
        }

        if not ucp_ids:
            return {}

        ucps = UserCompanyProfile.objects.select_related("profile").filter(
            pk__in=ucp_ids
        )

        recruiter_map = {}
        for ucp in ucps:
            if not ucp.profile:
                continue
            presentation = FileURLService.present_profile_images(ucp.profile)
            profile_image = (presentation.get("profile_image") or {}).get("file_path")
            recruiter_map[ucp.id] = {  # ucp.id is already int
                "full_name": ucp.profile.full_name,
                "profile_image_url": profile_image,
            }

        return recruiter_map
