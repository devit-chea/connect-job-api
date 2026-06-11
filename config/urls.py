"""
URL configuration for next_ping_api project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from settings.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.urls import path, include,re_path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView as RedocView,
    SpectacularSwaggerView as SwaggerView,
)
from django.conf.urls.static import static
urlpatterns = [
    # application.
    path(
        
        "api/",
        include(
            [
                path("", include("apps.core.urls")),
                path("", include("apps.base.urls")),
                path("", include("apps.auth_oauth.routes.auth_route")),
                path("", include("apps.recruiter_management.urls")),
                path("", include("apps.configuration.urls")),
                path("", include("apps.auth_totp_mail.urls")),
                path("", include("apps.job_management_app.routes.job_management_app_route")),
                path("", include("apps.activity_tracking_app.urls")),
                path("", include("apps.file_management_app.urls")),
                path("", include("apps.dashboard.urls")),
                path("", include("apps.elasticsearch_app.urls")),
                path("", include("apps.integration.urls")),
                re_path(r'^auth/', include('drf_social_oauth2.urls', namespace='drf'))

            ]
            + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
            + static(settings.STATIC_ASSET_URL, document_root=settings.STATIC_ASSET_ROOT)
            + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
        ),
    ),
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)


if settings.DEBUG:
    urlpatterns += [
        path("schema/", SpectacularAPIView.as_view(), name="schema"),
        path("swagger/", SwaggerView.as_view(url_name="schema"), name="swagger"),
        path("redoc/", RedocView.as_view(url_name="schema"), name="redoc"),
    ]
