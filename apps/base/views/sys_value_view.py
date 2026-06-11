from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from apps.base.models.sys_value_model import SysValue, SysValueCategories
from apps.base.serializers.sys_value_serializer import (
    SysValueCategoriesSerializer,
    SysValueSerializer,
)
from apps.base.views.base_views import BaseModelViewSet
from apps.base.mixins.permission_mixin import PermissionMixin


class PublicSysValueView(BaseModelViewSet):
    FIELDS: list[str] = [
        "id",
        "name",
        "description",
        "order_index",
        "default",
        "active",
        "properties",
        "category__name",
    ]
    permission_classes = [AllowAny]
    queryset = SysValue.objects.all()
    serializer_class = SysValueSerializer
    search_fields = FIELDS
    filterset_fields = FIELDS
    ordering_fields = FIELDS

    @action(
        methods=["get"],
        url_path=r"by/(?P<category>[0-9A-Za-z_-]+)",
        detail=False,
        permission_classes=[AllowAny],
    )
    def get_value_by_category(self, request, category, format=None):
        """
        Retrieves a list of SysValue objects filtered by their Category name
        """

        queryset = (
            SysValue.objects.filter(category__name=category, active=True)
            .exclude(is_other=True)
            .all()
        )
        data = self.filter_queryset(queryset)
        page = self.paginate_queryset(data)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SysValueView(PermissionMixin, BaseModelViewSet):
    FIELDS: list[str] = [
        "id",
        "name",
        "description",
        "order_index",
        "default",
        "active",
        "properties",
        "category__name",
    ]
    queryset = SysValue.objects.all()
    serializer_class = SysValueSerializer
    filterset_fields = FIELDS
    search_fields = FIELDS
    ordering_fields = FIELDS
    permission_codename = "operator_job_management_config"

    @action(
        methods=["get"],
        url_path="by/(?P<category>[0-9A-Za-z_-]+)",
        detail=False,
        permission_classes=[IsAuthenticated],
    )
    def get_value_by_category(self, request, category, format=None):
        queryset = (
            SysValue.objects.filter(category__name=category)
            .exclude(is_other=True)
            .all()
        )
        data = self.filter_queryset(queryset)
        page = self.paginate_queryset(data)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SysValueCategoriesView(PermissionMixin, BaseModelViewSet):
    queryset = SysValueCategories.objects.all()
    serializer_class = SysValueCategoriesSerializer
    search_fields = ["name"]
    permission_codename = "operator_job_management_config"
