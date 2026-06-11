import importlib
import logging

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError

from apps.core.exceptions.base_exceptions import BadRequestException
from apps.base.serializers.base_lookup_serializer import (
    BaseLookupSerializer,
    ContentTypeSerializer,
)


class BaseContentTypeView(generics.ListAPIView):
    permission_classes = ()
    queryset = ContentType.objects.all()
    serializer_class = ContentTypeSerializer


class BaseLookupView(generics.CreateAPIView):
    queryset = None
    serializer_class = BaseLookupSerializer
    filter_backends = [OrderingFilter, SearchFilter, DjangoFilterBackend]
    filterset_fields = "__all__"
    ordering_fields = "__all__"

    @property
    def model(self):
        serializer = BaseLookupSerializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        contenttype = ContentType.objects.filter(
            model=validated_data.get("contenttype")
        ).first()
        if not contenttype:
            raise BadRequestException("Class not Found.")
        model_class = contenttype.model_class()
        return model_class

    def get_mapping_class(self):
        try:
            mapping_class = self.request.data.get("mapping", None)
            mapping_class_list = mapping_class.split(".")

            module_name = ".".join(mapping_class_list[:-1])
            module = importlib.import_module(module_name)
            class_name = mapping_class_list[-1]

            serializer_class = getattr(module, class_name)
            return serializer_class
        except Exception as e:
            logging.error(e)
            return None

    def get_mapping_data(self, queryset):
        request_data = self.request.data
        serializer_class = self.get_mapping_class()

        try:
            serializer = serializer_class(
                data=request_data, context=self.get_serializer_context()
            )
        except Exception as e:
            logging.error(e)
            raise BadRequestException("Data mapping error.")

        queryset = self.filter_queryset(queryset)
        page = self.paginate_queryset(queryset)
        if request_data.get("paging", None):
            serializer = serializer_class(
                page, many=True, context=self.get_serializer_context()
            )
            return self.get_paginated_response(serializer.data)

        serializer = serializer_class(
            queryset, many=True, context=self.get_serializer_context()
        )
        return Response(serializer.data)

    def get_queryset(self):
        fields = self.request.data.get("fields", None)
        if fields != ["all"]:
            queryset = self.model.objects.values(*fields)
        else:
            queryset = self.model.objects.all()
        return queryset

    def create(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            if request.data.get("mapping", None):
                return self.get_mapping_data(queryset)

            queryset = self.filter_queryset(queryset)
            page = self.paginate_queryset(queryset)
            if request.data.get("paging", None):
                return self.get_paginated_response(page)
            return Response(queryset)

        except FieldError as e:
            raise BadRequestException(e)
        except Exception as ex:
            raise ex
