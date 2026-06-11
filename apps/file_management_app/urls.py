from django.urls import path, include, re_path
from rest_framework import routers

router = routers.DefaultRouter(trailing_slash=False)


urlpatterns = [
    path("", include(router.urls)),
    re_path(r"^wdg-storage/", include("wdg_storage.urls")),
]
