from django.urls import path, include
from rest_framework import routers

from apps.auth_oauth.views.telegram_auth_view import RecruiterTelegramSignupView
from apps.recruiter_management.views.recruiter_company_view import (
    CompanyRequestInformationView,
    RecruiterCompanyView,
    CompanyResubmitView,
    CompanyProfileRejectReasonView,
    RecruiterUpdateProfileCompanyView,
)
from apps.recruiter_management.views.recruiter_management_view import (
    RecruiterAdminCreateRecruiterView,
    RecruiterAdminRolesView,
)
from apps.recruiter_management.views.recruiter_schedule_view import (
    InvitationScheduleByApplicationView,
    RecruiterInvitationScheduleListView,
)
from apps.recruiter_management.views.recruiter_view import (
    RecruiterSignupView,
    RecruiterProfileCreateView,
    RecruiterCompanyProfileView,
    RecruiterCompanyProfileUpdateView,
    RecruiterProfessionalDetailUpdateView,
)

router = routers.DefaultRouter(trailing_slash=False)
router.register(
    r"recruiter_admin/users",
    RecruiterAdminCreateRecruiterView,
    basename="recruiter-admin-users",
)
router.register(
    r"recruiter_admin/roles", RecruiterAdminRolesView, basename="recruiter-admin-roles"
)
router.register(
    r"recruiter/companies", RecruiterCompanyView, basename="recruiter-companies"
)

urlpatterns = [
    path("", include(router.urls)),
    path(
        "recruiter/",
        include(
            [
                path("signup", RecruiterSignupView.as_view()),
                path("signup/telegram", RecruiterTelegramSignupView.as_view()),
                path("profile", RecruiterProfileCreateView.as_view()),
                path("profile/company", RecruiterCompanyProfileView.as_view()),
                path(
                    "profile/company/update",
                    RecruiterCompanyProfileUpdateView.as_view(),
                ),
                path(
                    "profile/professional-detail",
                    RecruiterProfessionalDetailUpdateView.as_view(),
                    name="recruiter-professional-detail",
                ),
            ]
        ),
    ),
    path(
        "recruiter/company-request-information", CompanyRequestInformationView.as_view()
    ),
    path("recruiter/resubmit-company", CompanyResubmitView.as_view()),
    path("recruiter/request-rejected-reason", CompanyProfileRejectReasonView.as_view()),
    path(
        "recruiter/company/update-profile", RecruiterUpdateProfileCompanyView.as_view()
    ),
    path(
        "recruiter/invitations-schedules",
        RecruiterInvitationScheduleListView.as_view(),
        name="invitation-schedule-list",
    ),
    path(
        "invitations/schedule/application/<int:job_application_id>/pipeline-config/<int:pipeline_config_id>/pipeline-step/<int:pipeline_step_id>",
        InvitationScheduleByApplicationView.as_view(),
        name="invitation-schedule-by-application",
    ),
]
