from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.integration.views.job_platform_view import (
    DropIntegrationView,
    InitializeHandshakeView,
    IntegrationExchangeView,
    ErpUserLookupProxyView,
)
from apps.integration.views.company_integration_view import (
    CompanyIntegrationLookupByDomainView,
    CompanyIntegrationRegisterView,
)

router = DefaultRouter(trailing_slash=False)

urlpatterns = [
    path(
        "v1/integration/",
        include(
            [
                path("initialize", InitializeHandshakeView.as_view()),
                path("exchange", IntegrationExchangeView.as_view()),
                path("look_up/users", ErpUserLookupProxyView.as_view()),
                path("disconnect", DropIntegrationView.as_view()),
                # Company Collection endpoints
                path(
                    "companies/register",
                    CompanyIntegrationRegisterView.as_view(),
                    name="integration-register",
                ),
                path(
                    "companies/lookup",
                    CompanyIntegrationLookupByDomainView.as_view(),
                    name="integration-lookup",
                ),
            ]
        ),
    ),
    path("", include(router.urls)),
]
