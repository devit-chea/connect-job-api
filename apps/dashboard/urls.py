from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.elasticsearch_app.views.elastic_recommend_applicant_view import (
    JobRecommendApplicantsViewSet,
    JobRecommendAllApplicantsViewSet,
)

from apps.dashboard.views.dashboard_job_views import (
    ApplicantHiringStageView,
    ApplicantMatchViewSet,
    ApplicationOverviewView,
    AppliedByCategoryView,
    DashboardRecruiterJobView,
    HeadcountByCategoryView,
    InterviewScheduleView,
    JobStatsView,
)

router = DefaultRouter(trailing_slash=False)
router.register(
    r"dashboard/recruiter/applicant-matches",
    ApplicantMatchViewSet,
    basename="applicant-matches",
)

urlpatterns = [
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
    # Dashboard recommend applicants for each job
    path(
        "dashboard/recruiter/jobs",
        DashboardRecruiterJobView.as_view(),
        name="dashboard-recruiter-jobs",
    ),
    # Dashboard for Admin Recruiter and Recruiter
    path("dashboard/job-stats", JobStatsView.as_view()),
    path("dashboard/headcount-by-category", HeadcountByCategoryView.as_view()),
    path("dashboard/applied-by-category", AppliedByCategoryView.as_view()),
    path("dashboard/application-overview", ApplicationOverviewView.as_view()),
    path("dashboard/application-hiring-stage", ApplicantHiringStageView.as_view()),
    path("dashboard/application-interview-stage", InterviewScheduleView.as_view()),
    path("", include(router.urls)),
]
