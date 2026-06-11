from django.urls import path, include
from rest_framework import routers

from apps.base.views.admin_company_view import AdminCompanyView
from apps.base.views.base_look_up_view import BaseLookupView, BaseContentTypeView
from apps.base.views.company_view import (
    ApplicantPublicCompanyView,
    ApplicantCompanyView,
    VerifiedCompaniesListView,
)
from apps.base.views.country_view import CountryView
from apps.base.views.currency_view import CurrencyView
from apps.base.views.factory_view import (
    CountriesView,
    ResLanguageView,
    GeoAreasView,
    InstitutionsView,
    PermissionView,
)
from apps.base.views.geo_view import GeoAreaByParentView, GeoView
from apps.base.views.industry_view import (
    IndustryListCreateView,
    IndustryRetrieveUpdateDestroyView,
)
from apps.base.views.institution_view import InstitutionView
from apps.base.views.language_view import LanguageView
from apps.base.views.sequence_view import SequenceView
from apps.base.views.sys_setting_view import SysSettingView
from apps.base.views.sys_value_view import (
    SysValueCategoriesView,
    SysValueView,
    PublicSysValueView,
)
from apps.base.views.mobile_app_view import (
    CheckForceUpdateView,
    PublicMobileAppLinkView,
)

router = routers.DefaultRouter(trailing_slash=False)
router.register(r"sys_value_category", SysValueCategoriesView)
router.register(r"sys_value", SysValueView)
router.register(r"sys_setting", SysSettingView)
router.register(r"companies", ApplicantCompanyView, basename="applicant-company-detail")
router.register(r"operator/companies", AdminCompanyView, basename="operator-companies")
router.register(r"sequences", SequenceView)
router.register(r"institution", InstitutionView)
router.register(r"languages", LanguageView)
router.register(r"countries", CountryView)
router.register(r"geo_areas", GeoView)
router.register(r"currencies", CurrencyView)
public_sys_value = PublicSysValueView.as_view(
    {
        "get": "get_value_by_category",
    }
)

urlpatterns = [
    path(
        "public/sys-values/by/<str:category>",
        public_sys_value,
        name="public-sys-values-by-category",
    ),
    path("factories/countries", CountriesView.as_view()),
    path("factories/geo_areas", GeoAreasView.as_view()),
    path("factories/language", ResLanguageView.as_view()),
    path("factories/institutions", InstitutionsView.as_view()),
    path("factories/permissions", PermissionView.as_view()),
    path(
        "factories/industries",
        IndustryListCreateView.as_view(),
        name="industry-list-create",
    ),
    path(
        "factories/industries/<int:pk>",
        IndustryRetrieveUpdateDestroyView.as_view(),
        name="industry-detail",
    ),
    path("lookup", BaseLookupView.as_view()),
    path("contenttypes", BaseContentTypeView.as_view()),
    path(
        "public/geo_areas/by-parent",
        GeoAreaByParentView.as_view(),
        name="geo_areas-by-parent-list",
    ),
    # ElasticSearch for List Public Company
    path(
        "companies",
        ApplicantPublicCompanyView.as_view({"get": "list"}),
        name="companies-list",
    ),
    path(
        "companies/verified",
        VerifiedCompaniesListView.as_view(),
        name="companies-verified",
    ),
    # Mobile App Force Update
    path(
        "check_force_update",
        CheckForceUpdateView.as_view(),
        name="check-force-update",
    ),
    # Mobile App Install Link
    path("install", PublicMobileAppLinkView.as_view()),
    path("", include(router.urls)),
]
