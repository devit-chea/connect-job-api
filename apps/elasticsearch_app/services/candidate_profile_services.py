from apps.elasticsearch_app.models.candidate_profile_document import (
    CandidateProfileDocument,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.elasticsearch_app.services.job_matching_service import (
    calculate_similarity_score,
)


class CandidateProfileService:
    @staticmethod
    def get_candidate_profile(user_profile_company_id: int):
        candidate_profile = (
            CandidateProfileDocument.search()
            .query("term", id=user_profile_company_id)
            .execute()
        )
        return candidate_profile

    @staticmethod
    def get_candidate_job_similarity_score(
        ucp_id: int,
        job_post_id: int,
    ) -> float:
        """
        Returns similarity score between a candidate and a job post.

        Fallback order:
        1. CandidateProfileService (index 0)
        2. UserCompanyProfile (DB)
        3. Return 0 if anything is missing or fails
        """

        if not ucp_id or not job_post_id:
            return 0

        job_post = JobPostModel.objects.filter(id=job_post_id).first()
        if not job_post:
            return 0

        candidate = None

        # 1️ Try service
        try:
            result = CandidateProfileService.get_candidate_profile(ucp_id)
            if result:
                candidate = result[0]
        except Exception:
            candidate = None

        # 2️ Fallback to DB
        if not candidate:
            candidate = UserCompanyProfile.objects.filter(pk=ucp_id).first()

        if not candidate:
            return 0

        return calculate_similarity_score(candidate, job_post)
