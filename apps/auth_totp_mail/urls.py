from django.urls import include, path
from rest_framework import routers

from apps.auth_totp_mail.views.applicant_invitation_view import JobApplicationInvitationViewSet
from apps.auth_totp_mail.views.invitation_views import (
    ApplicantUpcomingEventsView,
    InvitationDetailView,
    InvitationHistoryView,
    RescheduleInvitationView,
    SendInvitationView,
    UpdateInvitationStatusView,
)
from apps.auth_totp_mail.views.mail_template_config_views import (
    MailTemplateConfigViewSet,
)
from apps.auth_totp_mail.views.mail_template_views import (
    LoginResendOtpView,
    MailTemplateViewSet,
    ResendView,
    VerifyOTPResetPasswordView,
    VerifyOTPView,
    PasswordPreChangeVerifyOTPView,
)

router = routers.DefaultRouter(trailing_slash=False)

router.register(r"mail-templates-configs", MailTemplateConfigViewSet)
mail_template_list = MailTemplateViewSet.as_view(
    {
        "get": "list",
    }
)
mail_template_detail = MailTemplateViewSet.as_view(
    {
        "get": "retrieve",
    }
)
router.register(
    r"applicant/invitations/upcoming",
    ApplicantUpcomingEventsView,
    basename="applicant-upcoming-events",
)
router.register(
    r"applicant/job-applications/(?P<job_application_id>[^/.]+)/invitations",
    JobApplicationInvitationViewSet,
    basename="applicant-job-application-invitations",
)

urlpatterns = [
    path("mail-templates", mail_template_list, name="mailtemplate-list"),
    path("mail-templates/<int:pk>", mail_template_detail, name="mailtemplate-detail"),
    path("authtotp/mail/verify-otp", VerifyOTPView.as_view(), name="verify_otp"),
    path(
        "authtotp/mail/verify-otp-change-password",
        PasswordPreChangeVerifyOTPView.as_view(),
        name="pre-change-password",
    ),
    path("authtotp/mail/verify-otp", VerifyOTPView.as_view(), name="verify_otp"),
    path(
        "authtotp/mail/verify-otp-reset-password",
        VerifyOTPResetPasswordView.as_view(),
        name="verify_otp_reset_password",
    ),
    path("authtotp/mail/resend", ResendView.as_view(), name="resend"),
    path("authtotp/login/resend", LoginResendOtpView.as_view(), name="resend-otp"),
    path("invitations/send", SendInvitationView.as_view(), name="send-invitation"),
    path(
        "invitations/<int:invitation_id>",
        InvitationDetailView.as_view(),
        name="invitation-detail",
    ),
    path(
        "invitations/<int:job_application_id>/history",
        InvitationHistoryView.as_view(),
        name="invitation-history",
    ),
    path(
        "invitations/<int:invitation_id>/reschedule",
        RescheduleInvitationView.as_view(),
        name="reschedule-invitation",
    ),
    path(
        "invitations/<int:invitation_id>/status",
        UpdateInvitationStatusView.as_view(),
        name="update-invitation-status",
    ),
    path("", include(router.urls)),
]
