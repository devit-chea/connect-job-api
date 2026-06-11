from rest_framework import generics
from rest_framework.response import Response

from apps.base.views.base_views import BaseModelViewSet, BaseReadOnlyModelViewSet
from apps.base.models.sequence_model import Sequence
from apps.base.serializers.sequence_serializer import SequenceSerializer, SequenceReadOnlySerializer, SequencePreviewSerializer
from apps.base.mixins.sequence_mixin import SequenceMixin


class SequenceView(BaseModelViewSet):
    queryset = Sequence.objects.all()
    serializer_class = SequenceSerializer


class SequenceReadOnlyView(BaseReadOnlyModelViewSet):
    queryset = Sequence.objects.all()
    serializer_class = SequenceReadOnlySerializer


class SequencePreviewView(generics.CreateAPIView, SequenceMixin):
    serializer_class = SequencePreviewSerializer

    def create(self, request, *args, **kwargs):
        result = self.sequence_preview(request)
        return Response(result)
