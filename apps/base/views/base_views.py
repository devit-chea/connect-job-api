from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, views, status, response
from rest_framework import viewsets, mixins
from rest_framework.filters import SearchFilter, OrderingFilter

from apps.base.mixins.base_mixin import BaseMixin
from apps.base.mixins.custom_jwt_request_mixin import CustomJWTRequestMixin
from apps.base.mixins.query_scope_mixin import (
    AdminQuerysetMixin,
    AdminRecruiterQuerysetMixin,
    ApplicantQuerysetMixin,
    RecruiterQuerysetMixin,
)


class BaseReadOnlyViewSet(
    CustomJWTRequestMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
    BaseMixin,
):
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    filterset_fields = "__all__"
    ordering_fields = "__all__"


class BaseModelViewSet(CustomJWTRequestMixin, viewsets.ModelViewSet, BaseMixin):
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    filterset_fields = "__all__"
    ordering_fields = "__all__"

    def perform_create(self, serializer):
        self._perform_create(serializer)

    def perform_update(self, serializer):
        self._perform_update(serializer)


class BaseReadOnlyModelViewSet(CustomJWTRequestMixin, viewsets.ReadOnlyModelViewSet):
    pass


class BaseCreateAPIView(
    CustomJWTRequestMixin,
    generics.CreateAPIView,
    BaseMixin,
):
    def perform_create(self, serializer):
        self._perform_create(serializer)


class BaseUpdateAPIView(
    CustomJWTRequestMixin,
    generics.UpdateAPIView,
    BaseMixin,
):
    def perform_update(self, serializer):
        self._perform_update(serializer)


class BaseListAPIView(CustomJWTRequestMixin, generics.ListAPIView):
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    filterset_fields = "__all__"
    ordering_fields = "__all__"


class BaseRetrieveAPIView(CustomJWTRequestMixin, generics.RetrieveAPIView):
    pass


class BaseRetrieveUpdateAPIView(
    CustomJWTRequestMixin, generics.RetrieveUpdateAPIView, BaseMixin
):
    def perform_update(self, serializer):
        self._perform_update(serializer)


class BasePatchAPIView(CustomJWTRequestMixin, views.APIView, BaseMixin):
    serializer_class = None  # Child must override

    def get_object(self):
        """
        Child view must implement this to return the instance
        """
        raise NotImplementedError("get_object() must be implemented")

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()

        serializer = self.serializer_class(
            instance,
            data=request.data,
            partial=True,
            context=self.get_serializer_context(),
        )

        # Validation is done inside BaseMixin._perform_update
        self._perform_update(serializer)

        return response.Response(serializer.data, status=status.HTTP_200_OK)

    def get_serializer_context(self):
        ctx = {"request": self.request}
        if hasattr(self, "extra_context"):
            ctx.update(self.extra_context)
        return ctx


class BaseViewSet(CustomJWTRequestMixin, viewsets.ModelViewSet, BaseMixin):
    filter_backends = [SearchFilter, DjangoFilterBackend, OrderingFilter]
    filterset_fields = []
    ordering_fields = []

    def perform_create(self, serializer):
        self._perform_create(serializer)

    def perform_update(self, serializer):
        self._perform_update(serializer)


class RecruiterBaseViewSet(RecruiterQuerysetMixin, BaseViewSet):
    pass


class AdminRecruiterBaseViewSet(AdminRecruiterQuerysetMixin, BaseViewSet):
    pass


class AdminRecruiterOrRecruiterBaseViewSet(AdminRecruiterQuerysetMixin, BaseViewSet):
    pass


class ApplicantBaseViewSet(ApplicantQuerysetMixin, BaseViewSet):
    pass


class AdminBaseViewSet(AdminQuerysetMixin, BaseViewSet):
    pass
