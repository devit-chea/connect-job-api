import django_filters
from django.db.models import JSONField
from django_filters.rest_framework import DjangoFilterBackend


class JSONSafeFilterSet(django_filters.FilterSet):
    """
    FilterSet base that silently maps JSONField to a no-op CharFilter instead of
    raising AssertionError when filterset_fields = "__all__" encounters a JSONField.
    """

    @classmethod
    def filter_for_field(cls, f, field_name, lookup_expr=None):
        if isinstance(f, JSONField):
            return django_filters.CharFilter(field_name=field_name, lookup_expr="icontains")
        return super().filter_for_field(f, field_name, lookup_expr)


class SafeDjangoFilterBackend(DjangoFilterBackend):
    filterset_base = JSONSafeFilterSet
