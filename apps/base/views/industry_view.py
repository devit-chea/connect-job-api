from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.base.models.industry_model import IndustryModel
from apps.base.serializers.industry_serializer import IndustrySerializer


class IndustryListCreateView(generics.ListCreateAPIView):
    queryset = IndustryModel.objects.all()
    serializer_class = IndustrySerializer
    permission_classes = [AllowAny]

class IndustryRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = IndustryModel.objects.all()
    serializer_class = IndustrySerializer
    permission_classes = [AllowAny]