from django.urls import include, path
from apps.elasticsearch_app.views.elastic_recommend_job_view import ElasticSearchRecommendJobView
from apps.elasticsearch_app.views.elastic_similar_job_view import SimilarJobView
from rest_framework.routers import DefaultRouter

from apps.elasticsearch_app.views.elastic_candidate_profile_view import (
    CandidateProfileView,
)
from apps.elasticsearch_app.views.elastic_global_search_view import (
    GlobalSearchAPIView,
    PeopleProfileSearchView,
    PeopleProfileDetailView,
)
from apps.elasticsearch_app.views.elastic_job_post_view import (
    ElasticSearchExploreJobView,
    ElasticSearchForYouJobView,
)
from apps.elasticsearch_app.views.elastic_recommend_applicant_view import (
    JobRecommendApplicantsViewSet,
    JobRecommendAllApplicantsViewSet,
)
from apps.elasticsearch_app.views.elastic_search_suggestion_view import (
    GlobalSuggestionAPIView,
)
from apps.job_management_app.views.job_application_views import (
    JobApplicationView,
    RecruiterJobListApplicantsView,
    RecruiterJobApplicationView,
)

from apps.job_management_app.views.job_category_view import JobCategoryPublicView, JobCategoryView
from apps.job_management_app.views.job_pipeline_config_view import (
    JobPipelineConfigView,
    JobPipelineStatusConfigView,
    OperatorJobPipelineStatusConfigView,
    OperatorJobPipelineConfigView,
    StepStatusesListView,
)
from apps.job_management_app.views.job_post_view import (
    CompanyJobPostListView,
    RecruiterApplicationPipelineUpdateView,
    RecruiterJobPostListView,
    RecruiterJobPostView,
    JobPostQuestionView,
    JobPostCountsView,
    ApplicantJobPostView, OperatorJobPostView, JobPostCategoryListView, RecruiterJobPostStatusUpdateView,
    CompanyRecruitersListView,
)
from apps.job_management_app.views.job_repost_view import JobPostRepostView

router = DefaultRouter(trailing_slash=False)
# operator
router.register(
    r"operator/jop_pipeline_status_config",
    OperatorJobPipelineStatusConfigView,
    basename="operator-job-pipeline-status-config",
)
router.register(
    r"operator/job_pipeline_config",
    OperatorJobPipelineConfigView,
    basename="operator-job-pipeline-config",
)
router.register(
    r"operator/job_post", OperatorJobPostView, basename="operator-job_post"
)

router.register(
    r"recruiter/job_post", RecruiterJobPostView, basename="recruiter-job_post"
)
router.register(r"job_post", ApplicantJobPostView)
router.register(
    r"candidate_profile_es", CandidateProfileView, basename="candidate-profile-es"
)
router.register(
    r"job_pipeline_config", JobPipelineConfigView, basename="job-pipeline-config"
)
router.register(
    r"jop_pipeline_status_config",
    JobPipelineStatusConfigView,
    basename="job-pipeline-status-config",
)
router.register(
    r"operator/job-category", JobCategoryView, basename="operator-job-category"
)

recruiter_app_list = RecruiterJobApplicationView.as_view({"get": "list"})
recruiter_app_detail = RecruiterJobApplicationView.as_view({"get": "retrieve"})
explore_job_view = ElasticSearchExploreJobView.as_view({"get": "list"})
for_you_job_view = ElasticSearchForYouJobView.as_view({"get": "list"})
questions_job_view = JobPostQuestionView.as_view({"get": "list"})
recommend_job_view = ElasticSearchRecommendJobView.as_view({"get": "list"})

job_application_rud_view = JobApplicationView.as_view(
    {
        "get": "retrieve",
        "delete": "destroy",
    }
)
job_application_list_view = JobApplicationView.as_view({"get": "list"})
job_application_statuses_view = JobApplicationView.as_view({
    'get': 'application_statuses',
})


urlpatterns = [
    path(
        "job_post/counts/<str:by>", JobPostCountsView.as_view(), name="job-post-counts"
    ),
    path(
        "job_post/categories",
        JobPostCategoryListView.as_view(),
        name="job_post-categories-listing",
    ),
    # ElasticSearch job discovery
    path("job_post/explore", explore_job_view, name="job-post-explore"),
    path("job_post/for_you", for_you_job_view, name="job-post-for-you"),
    path("applicant/job-post/recommend", recommend_job_view, name="job-post-recommend"),
    # Job post routes
    path("job_post/<int:pk>/questions", questions_job_view, name="job-post-questions"),
    # Search suggestion
    path(
        "search/suggestions",
        GlobalSuggestionAPIView.as_view(),
        name="search-suggestions",
    ),
    # Job application routes
    path(
        "job_application", job_application_list_view, name="job-application-list"
    ),  # list all user apps
    path(
        "job_application/<int:pk>",
        job_application_rud_view,
        name="job-application-detail",
    ),  # get/update/delete
    path(
        "recruiter/list-applicants/by-job/<job_post_id>",
        RecruiterJobListApplicantsView.as_view(),
        name="recruiter-job-applicant-list",
    ),
    path(
        "job_application/<int:pk>/application-statuses",
        job_application_statuses_view,
        name="job-application-statuses",
    ),
    # Default router
    path(
        "recruiter/job_applications",
        recruiter_app_list,
        name="recruiter-applications-list",
    ),
    path(
        "recruiter/<int:pk>/employment-status",
        RecruiterJobApplicationView.as_view({"patch": "update_employment_status"}),
        name="recruiter-app-update-status",
    ),
    path(
        "recruiter/steps/<pk>/statuses",
        StepStatusesListView.as_view(),
        name="step-statuses-list",
    ),
    path(
        "recruiter/job_applications/<int:pk>",
        recruiter_app_detail,
        name="recruiter-applications-detail",
    ),
    path(
        "company/<int:company_id>/job-posts",
        CompanyJobPostListView.as_view(),
        name="company-job-posts-list",
    ),
    path(
        "recruiter/<int:create_ucp_id>/job-posts",
        RecruiterJobPostListView.as_view(),
        name="recruiter-job-posts-list",
    ),
    path(
        "recruiter/company-recruiters",
        CompanyRecruitersListView.as_view(),
        name="recruiter-company-recruiters",
    ),
    path(
        "recruiter/job_post/<int:pk>/status",
        RecruiterJobPostStatusUpdateView.as_view(),
        name="recruiter-job-post-status-update",
    ),
    # ElasticSearch for Global Search
    path("global-search", GlobalSearchAPIView.as_view(), name="global-search"),
    # ElasticSearch for People Profile
    path(
        "people-profile",
        PeopleProfileSearchView.as_view({"get": "list"}),
        name="people-profile",
    ),
    path(
        "people-profile/<int:pk>",
        PeopleProfileDetailView.as_view({"get": "retrieve"}),
        name="people-profile-detail",
    ),
    # ElasticSearch recommend applicants for each job
    # Recommend for applicants who apply to job.
    path(
        "recruiter/jobs/<int:pk>/recommend-applicants",
        JobRecommendApplicantsViewSet.as_view(),
        name="job-recommend-applicants",
    ),
    # Recommend for all applicants profile.
    path(
        "recruiter/jobs/<int:pk>/recommend-all-applicants",
        JobRecommendAllApplicantsViewSet.as_view(),
        name="job-recommend-all-applicants",
    ),
    # Similar Job for Applicants
    path("jobs/<int:id>/similar", SimilarJobView.as_view(), name="similar-jobs"),
    path(
        "public/job-categories",
        JobCategoryPublicView.as_view(),
        name="job-categories-list",
    ),
    path(
        "v2/recruiter/job_post/<int:job_post_id>/applications/<int:application_id>/pipeline",
        RecruiterApplicationPipelineUpdateView.as_view(),
        name="update-application-pipeline",
    ),
    path("recruiter/job-posts/<int:job_post_id>/repost", JobPostRepostView.as_view()),
    path("", include(router.urls)),
]
