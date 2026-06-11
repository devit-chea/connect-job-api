from django.urls import path, include
from rest_framework import routers

from apps.configuration.views.applicant_config_view import ApplicantConfigView
from apps.configuration.views.job_question_template_config_view import (
    JobQuestionTemplateConfigViewSet,
    OperatorJobQuestionTemplateConfigViewSet,
)

router = routers.DefaultRouter(trailing_slash=False)
router.register(r"applicant_config", ApplicantConfigView)
router.register(
    r"question_templates",
    JobQuestionTemplateConfigViewSet,
    basename="question_templates",
)

# operator
router.register(
    r"operator/question_templates",
    OperatorJobQuestionTemplateConfigViewSet,
    basename="operator-question_templates",
)
urlpatterns = [
    path("", include(router.urls)),
]
