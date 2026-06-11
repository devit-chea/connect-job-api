from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from apps.base.views.base_views import BaseModelViewSet, BaseListAPIView
from apps.base.models.geo_area_model import GeoArea
from apps.base.serializers.geo_area_serializer import GeoAreaSerializer


class GeoView(BaseModelViewSet):
    queryset = GeoArea.objects.all()
    serializer_class = GeoAreaSerializer
    filterset_fields = [
        "name",
        "name_kh",
        "parent_id",
    ]
    search_fields = [
        "name",
        "name_kh",
    ]

    @action(
        methods=["get"],
        url_path="by/(?P<country_id>[0-9]+)",
        detail=False,
        permission_classes=[],
    )
    def get_value_by_category(self, request, country_id, format=None):
        queryset = GeoArea.objects.filter(country_id=country_id).all()
        data = self.filter_queryset(queryset)
        page = self.paginate_queryset(data)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    
class GeoAreaByParentView(BaseListAPIView):
    serializer_class = GeoAreaSerializer
    permission_classes = [AllowAny]
    
    filterset_fields = [
        "name",
        "name_kh",
        "parent_id",
    ]
    search_fields = [
        "name",
        "name_kh",
    ]
    
    def get_queryset(self):
        """
        Return only GeoArea objects where parent_id is 0.
        """
        return GeoArea.objects.filter(parent_id=0)

    
