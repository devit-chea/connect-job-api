from apps.activity_tracking_app.models.job_post_user_state_model import (
    JobPostUserStateModel,
)


class JobPostStateService:
    @staticmethod
    def get_user_job_states(user_company_profile, job_ids):
        if not user_company_profile or not job_ids:
            return set(), set()

        qs = JobPostUserStateModel.objects.filter(
            user_company_profile=user_company_profile,
            job_post_id__in=job_ids,
        ).values("job_post_id", "status", "is_saved")

        saved_ids = {row["job_post_id"] for row in qs if row["is_saved"]}
        applied_ids = {row["job_post_id"] for row in qs if row["status"] == "applied"}

        return saved_ids, applied_ids
