from django.urls import path

from apps.elasticsearch_app.views.elastic_admin_view import RebuildSearchIndexView

urlpatterns = [
    path(
        "admin/search-index/rebuild",
        RebuildSearchIndexView.as_view(),
        name="search-index-rebuild",
    ),
]
