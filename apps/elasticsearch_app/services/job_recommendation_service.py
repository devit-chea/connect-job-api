import logging
from apps.activity_tracking_app.services.job_post_state_service import (
    JobPostStateService,
)
from apps.core.exceptions.base_exceptions import BadRequestException
from apps.elasticsearch_app.queries.job_post_builder_query import JobPostBuilderQuery
from apps.elasticsearch_app.queries.job_similarity_query import (
    build_job_similarity_query,
)
from apps.elasticsearch_app.queries.smart_score_query import (
    build_smart_score_query,
    build_smart_score_query_for_you,
)
from apps.elasticsearch_app.services.candidate_profile_services import (
    CandidateProfileService,
)


logger = logging.getLogger(__name__)


class JobRecommendationService:

    @staticmethod
    def get_explore_job(
        self,
        user=None,
        query_string=None,
        filters=None,
        ordering=None,
        page=1,
        page_size=10,
    ):
        qb = JobPostBuilderQuery()
        try:
            if user and user.is_authenticated:
                qb = JobRecommendationService._get_es_user_profile(
                    qb, self, user, build_smart_score_query, page, page_size
                )
                if qb.search.count() > 0:
                    qb = JobPostBuilderQuery()
                    qb.base_filter()
                    qb.apply_search(query_string)
                    qb.apply_filter(filters)
                    qb.apply_sort(ordering)
                    qb.apply_pagination(page, page_size)
                    return qb.build()

                # Reset if no results found for "Smart Score"
                qb = JobPostBuilderQuery()

        except Exception as e:
            raise BadRequestException(f"Get explore job error {e.args}")

        # Standard Build Process
        qb.base_filter()

        # Improvement: Only apply search if query_string has content
        # If empty, it stays as a 'filter' only query, which shows all
        if query_string and query_string.strip():
            qb.apply_search(query_string)

        qb.apply_filter(filters)
        qb.apply_sort(ordering)
        qb.apply_pagination(page, page_size)

        return qb.build()

    @staticmethod
    def get_for_you_job(
        self,
        user=None,
        query_string=None,
        filters=None,
        ordering=None,
        page=1,
        page_size=10,
    ):
        qb = JobPostBuilderQuery()

        try:
            if user and user.is_authenticated:
                qb = JobRecommendationService._get_es_user_profile(
                    qb, self, user, build_smart_score_query_for_you, page, page_size
                )
                # Check if the similarity query returned any results
                temp_search = qb.search
                if temp_search.count() == 0:
                    qb = JobPostBuilderQuery()
                    qb.base_filter()
                    qb.apply_search(query_string)
                    qb.apply_filter(filters)
                    qb.apply_sort(ordering)
                    qb.apply_pagination(page, page_size)
                    return qb.build()
        except Exception as e:
            raise BadRequestException(f"Get for you job error ({e.args},)")

        qb.base_filter()
        qb.apply_search(query_string)
        qb.apply_filter(filters)
        qb.apply_sort(ordering)
        qb.apply_pagination(page, page_size)

        return qb.build()

    @staticmethod
    def attach_user_states(user, jobs):
        """
        Add is_saved and is_applied to each job.
        Convert ES Document objects to dict for the serializer.
        """
        job_list = []
        for job in jobs:
            # Convert Document to dict if needed
            if hasattr(job, "to_dict"):
                job_data = job.to_dict()
            else:
                job_data = dict(job)  # if already dict

            # Default False if user not authenticated
            job_data["is_saved"] = False
            job_data["is_applied"] = False

            job_list.append(job_data)

        if not user or not user.is_authenticated:
            return job_list

        job_ids = [job["id"] for job in jobs]
        user_company_profile_id = getattr(user, "default_user_profile_company", None)
        saved_ids, applied_ids = JobPostStateService.get_user_job_states(
            user_company_profile_id, job_ids
        )
        for job_data in job_list:
            job_data["is_saved"] = job_data["id"] in saved_ids
            job_data["is_applied"] = job_data["id"] in applied_ids

        return job_list

    @staticmethod
    def _get_es_user_profile(qb, self, user, d, page, page_size):
        if not user:
            return qb

        try:
            user_company_profile_id = self.request.auth.payload.get(
                "user_company_profile_id", None
            )
            if user_company_profile_id:
                profile = CandidateProfileService.get_candidate_profile(
                    user_company_profile_id
                )
                if profile:
                    # Inject raw Search object into builder
                    qb.search = d(profile[0], page, page_size)
            return qb
        except Exception as e:
            raise BadRequestException(f"Get explore job error ({e.args},)")

    @staticmethod
    def get_explore_job_search(
        self,
        user=None,
        query_string=None,
        filters=None,
        ordering=None,
        page=1,
        page_size=10,
    ):
        def build_and_execute(fields=None):
            qb = JobPostBuilderQuery()
            qb.base_filter()
            if query_string and query_string.strip():
                qb.apply_search(query_string, fields=fields)
            qb.apply_filter(filters)
            qb.apply_sort(ordering)
            qb.apply_pagination(page, page_size)
            search_obj = qb.build()
            return search_obj.count(), search_obj.execute()

        try:
            if user and user.is_authenticated:
                qb = JobPostBuilderQuery()
                qb = JobRecommendationService._get_es_user_profile(
                    qb, self, user, build_smart_score_query, page, page_size
                )
                if qb.search.count() > 0:
                    total_count, job_list = build_and_execute(fields=["title^3"])
                    return total_count, JobRecommendationService.attach_user_states(user, job_list)

        except Exception as e:
            logger.error(f"Error in job service: {e.args}")
            return 0, []

        total_count, job_list = build_and_execute(fields=["title^3"])
        return total_count, JobRecommendationService.attach_user_states(user, job_list)