from apps.base.views.base_views import BaseModelViewSet
from apps.base.models.currency_model import Currency
from apps.base.serializers.currency_serializer import CurrencySerializer

class CurrencyView(BaseModelViewSet):
    queryset = Currency.objects.all()
    serializer_class = CurrencySerializer