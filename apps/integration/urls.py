from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.integration.views.job_platform_view import (
    DropIntegrationView,
    InitializeHandshakeView,
    IntegrationExchangeView,
    ErpUserLookupProxyView,
    JobCategoryLookupView,
)
from apps.integration.views.company_integration_view import (
    CompanyIntegrationLookupByDomainView,
    CompanyIntegrationRegisterView,
)
from apps.integration.views.data_mapping_view import (
    DataMappingListView,
    DataMappingDetailView,
    RestoreDefaultMappingsView,
    ValueMappingListView,
    ValueMappingDetailView,
)
from apps.integration.views.inbound_job_post_view import IntegrationJobPostView

router = DefaultRouter(trailing_slash=False)

urlpatterns = [
    path(
        "v1/integration/",
        include(
            [
                path("initialize", InitializeHandshakeView.as_view()),
                path("exchange", IntegrationExchangeView.as_view()),
                path("look_up/users", ErpUserLookupProxyView.as_view()),
                path("look_up/categories", JobCategoryLookupView.as_view(), name="integration-lookup-categories"),
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
                # Inbound job posting from ERP
                path(
                    "jobs/publish",
                    IntegrationJobPostView.as_view(),
                    name="integration-jobs-publish",
                ),
                # Data Mapping endpoints
                path(
                    "data-mapping/restore-defaults",
                    RestoreDefaultMappingsView.as_view(),
                    name="integration-data-mapping-restore-defaults",
                ),
                path(
                    "data-mapping",
                    DataMappingListView.as_view(),
                    name="integration-data-mapping-list",
                ),
                path(
                    "data-mapping/<uuid:pk>",
                    DataMappingDetailView.as_view(),
                    name="integration-data-mapping-detail",
                ),
                path(
                    "data-mapping/<uuid:field_mapping_id>/values",
                    ValueMappingListView.as_view(),
                    name="integration-value-mapping-list",
                ),
                path(
                    "data-mapping/<uuid:field_mapping_id>/values/<uuid:pk>",
                    ValueMappingDetailView.as_view(),
                    name="integration-value-mapping-detail",
                ),
            ]
        ),
    ),
    path("", include(router.urls)),
]
