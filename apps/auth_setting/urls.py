from django.urls import path
from .views import BulkToggle2StepVerificationView as BulkToggle

urlpatterns = [
    path(
        "bulk/toggle/two-step-verification",
        BulkToggle.as_view(),
        name="bulk_toggle_two_step_verification",
    )
]
