from django.urls import include, path
from rest_framework import routers

from apps.auth_oauth.views.admin_view import (
    OperatorUserView,
    OperatorAllRequestView,
    OperatorApprovalView,
    OperatorCurrentUserView,
    OperatorRequestDetailView,
    OperatorRolesView,
    OperatorRoleListView,
)
from apps.auth_oauth.views.altcha_view import AltchaChallengeAPIView
from apps.auth_oauth.views.applicant_view import (
    ApplicantSignupView,
    ApplicantProfileSignupView,
    ApplicantToRecruiterSignupView,
    ApplicantPreferenceView,
    ApplicantActivePreferenceView,
)
from apps.auth_oauth.views.auth_user_view import (
    CustomTokenRefreshView,
    LogoutView,
    DeleteAccountView,
)
from apps.auth_oauth.views.cv_scan_view import (
    CVExtractAPIView,
    ProfileCVScanSaveView,
    ProfileCVScanUpdateView,
)
from apps.auth_oauth.views.mobile_view import (
    MobileActiveProfileView,
    MobileUpdateActiveProfileView,
    MobileSkillView,
    MobileLanguageView,
    MobileEducationView,
    MobileWorkExperienceView,
    MobileLinkView,
    MobileProfileDocumentView,
)
from apps.auth_oauth.views.password_generator_view import password_generator_api
from apps.auth_oauth.views.profile_view import (
    ApplicantProfileUpdateView,
    ApplicantActiveProfileRetrieveView,
    MyProfileDocumentByTypeView,
    WorkExperiencesActiveProfileView,
    EducationsActiveProfileView,
    SkillsActiveProfileView,
    ReferencesActiveProfileView,
    PortfoliosActiveProfileView,
    LanguagesProfileActiveProfileView,
    WorkExperiencesProfileView,
    EducationsProfileView,
    SkillsProfileView,
    PortfoliosProfileView,
    ReferencesProfileView,
    LanguagesProfileView,
    ProfileDocumentView,
    RecruiterListApplicantWorkExperiencesView,
    RecruiterListApplicantSkillsView,
    RecruiterListApplicantEducationsView,
    RecruiterListApplicantLanguagesView,
)
from apps.auth_oauth.views.social_media_view import (
    GoogleCallbackView,
    LinkedinCallbackView,
    LinkedinMobileCallbackView,
    UserAuthenticationRedirectUrlView,
    MobileAppleIntegrationView,
)
from apps.auth_oauth.views.social_media_view import (
    MobileGoogleIntegrationView,
    MobileLinkedInIntegrationView,
)
from apps.auth_oauth.views.telegram_auth_view import (
    ApplicantTelegramSignupView,
    TelegramBotWebhookView,
    TelegramLoginView,
    RecruiterTelegramSignupView,
    TelegramResetPasswordView,
    MobileTelegramIntegrationView,
    TelegramAuthorizeView,
    TelegramOAuthCallbackView,
    TestFetchRedirect,
)
from apps.auth_oauth.views.views import (
    CurrentUserView,
    UnLockUserApi,
    ChangePassWordApi,
    ResetPasswordValidateToken,
    CheckAuthView,
    LoginView,
    AdminLoginView,
    ResetPasswordView,
    ResetPasswordChangePasswordView,
    SwitchProfileView,
    MobileLoginView,
    PermissionUserView,
    PermissionView,
    ChangePasswordView,
)

router = routers.DefaultRouter(trailing_slash=False)
router.register(r"operator/roles", OperatorRolesView)
router.register(r"operator/user", OperatorUserView, basename="operator-user")
router.register(
    r"mobile/profile-documents",
    MobileProfileDocumentView,
    basename="mobile-profile-documents",
)
router.register(r"mobile/educations", MobileEducationView, basename="mobile-educations")
router.register(r"mobile/skills", MobileSkillView, basename="mobile-skills")
router.register(r"mobile/languages", MobileLanguageView, basename="mobile-languages")
router.register(
    r"mobile/work_experiences",
    MobileWorkExperienceView,
    basename="mobile-work_experiences",
)
router.register(r"mobile/links", MobileLinkView, basename="mobile-links")
router.register(
    r"profile/work_experiences", WorkExperiencesProfileView, basename="work_experiences"
)
router.register(r"profile/educations", EducationsProfileView, basename="educations")
router.register(r"profile/skills", SkillsProfileView, basename="skills")
router.register(r"profile/references", ReferencesProfileView, basename="references")
router.register(r"profile/languages", LanguagesProfileView, basename="languages")
router.register(r"profile/portfolios", PortfoliosProfileView, basename="portfolios")
router.register(r"profile-documents", ProfileDocumentView, basename="profile-documents")
urlpatterns = [
    path("current_user", CurrentUserView.as_view()),
    path("permissions_user", PermissionUserView.as_view()),
    path("permissions", PermissionView.as_view()),
    path("switch_profile/<int:pk>", SwitchProfileView.as_view()),
    path("login", LoginView.as_view(), name="login"),
    path(
        "telegram/login",
        TelegramLoginView.as_view(),
        name="login with telegram phone number",
    ),
    path("operator/login", AdminLoginView.as_view(), name="operator-login"),
    path(
        "auth_provider_url",
        UserAuthenticationRedirectUrlView.as_view(),
        name="auth_provider_url",
    ),
    path("account/delete", DeleteAccountView.as_view(), name="user delete account"),
    path("logout", LogoutView.as_view(), name="user-logout"),
    path(
        "refresh_token",
        CustomTokenRefreshView.as_view(),
        name="refresh-token",
    ),
    path(
        "change_password",
        ChangePassWordApi.as_view(),
        name="change_password",
    ),
    path("unlock_user/<int:pk>", UnLockUserApi.as_view(), name="unlock_user"),
    path("password_reset", ResetPasswordView.as_view()),
    path(
        "reset_password/telegram",
        TelegramResetPasswordView.as_view(),
        name="telegram-reset-password",
    ),
    path("password_reset_change_password", ResetPasswordChangePasswordView.as_view()),
    path(
        "password_require_change",
        ChangePasswordView.as_view(),
        name="change-password when user required reset password",
    ),
    path(
        "password_reset/validate_token/",
        ResetPasswordValidateToken.as_view(),
    ),
    path("check_auth", CheckAuthView.as_view()),
    path("google/callback", GoogleCallbackView.as_view()),
    path("linkedin/callback", LinkedinCallbackView.as_view()),
    path("linkedin/mobile_callback", LinkedinMobileCallbackView.as_view()),
    # applicant
    path(
        "applicant/",
        include(
            [
                path("signup", ApplicantSignupView.as_view()),
                path(
                    "signup/telegram",
                    ApplicantTelegramSignupView.as_view(),
                    name="telegram-signup",
                ),
                path(
                    "webhook/telegram",
                    TelegramBotWebhookView.as_view(),
                    name="telegram-webhook",
                ),
                path("preference", ApplicantPreferenceView.as_view()),
                path("active_preference", ApplicantActivePreferenceView.as_view()),
                path("profile", ApplicantProfileSignupView.as_view()),
                path("become_recruiter", ApplicantToRecruiterSignupView.as_view()),
            ]
        ),
    ),
    path(
        "recruiter/",
        include(
            [
                path(
                    "profiles/<int:profile_id>/work-experiences",
                    RecruiterListApplicantWorkExperiencesView.as_view(),
                    name="recruiter-profile-work-experiences",
                ),
                path(
                    "profiles/<int:profile_id>/educations",
                    RecruiterListApplicantEducationsView.as_view(),
                    name="recruiter-profile-educations",
                ),
                path(
                    "profiles/<int:profile_id>/skills",
                    RecruiterListApplicantSkillsView.as_view(),
                    name="recruiter-profile-skills",
                ),
                path(
                    "profiles/<int:profile_id>/languages",
                    RecruiterListApplicantLanguagesView.as_view(),
                    name="recruiter-profile-languages",
                ),
            ]
        ),
    ),
    path("operator/generate_password", password_generator_api),
    path("operator/request/all", OperatorAllRequestView.as_view()),
    path("operator/request/approval/<int:pk>", OperatorApprovalView.as_view()),
    path("operator/request/<int:pk>", OperatorRequestDetailView.as_view()),
    # path("operator/send_invite/<int:pk>", OperatorSendInviteView.as_view()),
    path("operator/current_user", OperatorCurrentUserView.as_view()),
    path("operator/roles/<company>/<type>", OperatorRoleListView.as_view()),
    # mobile login
    path("mobile/login", MobileLoginView.as_view(), name="mobile-login"),
    path(
        "mobile/login_with_google",
        MobileGoogleIntegrationView.as_view(),
        name="mobile_login_with_google",
    ),
    path(
        "mobile/login_with_linkedin",
        MobileLinkedInIntegrationView.as_view(),
        name="mobile_login_with_linkedin",
    ),
    path(
        "mobile/login_with_apple",
        MobileAppleIntegrationView.as_view(),
        name="mobile_login_with_apple",
    ),
    # Telegram OIDC (applicant-only)'
    path(
        "auth/telegram/authorize",
        TelegramAuthorizeView.as_view(),
        name="telegram-authorize",
    ),
    path(
        "auth/telegram/callback",
        TelegramOAuthCallbackView.as_view(),
        name="telegram-oauth-callback",
    ),
    path(
        "mobile/login_with_telegram",
        MobileTelegramIntegrationView.as_view(),
        name="mobile-telegram-login-with-telegram-code",
    ),
    path(
        "mobile/test_redirect",
        TestFetchRedirect.as_view(),
        name="mobile-test",
    ),
    # profile for mobile
    path("mobile/active_profile", MobileActiveProfileView.as_view()),
    path("mobile/update_active_profile", MobileUpdateActiveProfileView.as_view()),
    # profile for web
    path("profile/active_profile", ApplicantActiveProfileRetrieveView.as_view()),
    path("profile/update_active_profile", ApplicantProfileUpdateView.as_view()),
    path(
        "profile/work_experiences/active_profile",
        WorkExperiencesActiveProfileView.as_view(),
    ),
    path("profile/educations/active_profile", EducationsActiveProfileView.as_view()),
    path("profile/skills/active_profile", SkillsActiveProfileView.as_view()),
    path("profile/references/active_profile", ReferencesActiveProfileView.as_view()),
    path("profile/portfolios/active_profile", PortfoliosActiveProfileView.as_view()),
    path(
        "profile/languages/active_profile", LanguagesProfileActiveProfileView.as_view()
    ),
    # CV Scanned data
    path(
        "profile/cv-scan/save",
        ProfileCVScanSaveView.as_view(),
        name="profile-cv-scan-save",
    ),
    path(
        "profile/cv-scan/<int:pk>/update",
        ProfileCVScanUpdateView.as_view(),
        name="profile-cv-scan-update",
    ),
    path("profile/cv/extract", CVExtractAPIView.as_view(), name="profile-cv-extract"),
    # My Profile Document by Type
    path(
        "profile-documents/by-type/<str:document_type>",
        MyProfileDocumentByTypeView.as_view(),
        name="profile-document-by-type",
    ),
    path(
        "mobile/profile-documents/by-type/<str:document_type>",
        MyProfileDocumentByTypeView.as_view(),
        name="mobile-profile-document-by-type",
    ),
    # Altcha Challenge
    path("altcha/challenge", AltchaChallengeAPIView.as_view(), name="altcha-challenge"),
    path("", include(router.urls)),
]
