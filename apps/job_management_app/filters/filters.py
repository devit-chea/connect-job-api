from django.contrib.postgres.fields import DecimalRangeField
from django.db.backends.postgresql.psycopg_any import NumericRange
from django_filters import rest_framework as filters
from apps.job_management_app.models.job_post_model import JobPostModel


class JobPostFilter(filters.FilterSet):
    salary_min = filters.NumberFilter(method="filter_salary_min")
    salary_max = filters.NumberFilter(method="filter_salary_max")

    class Meta:
        model = JobPostModel
        exclude = ["salary_range"]

        filter_overrides = {
            DecimalRangeField: {
                "filter_class": filters.CharFilter,
                "extra": lambda f: {"lookup_expr": "exact"},
            },
        }

    @staticmethod
    def filter_salary_min(queryset, name, value):
        return queryset.filter(salary_range__contains=value)

    @staticmethod
    def filter_salary_max(queryset, name, value):
        return queryset.filter(salary_range__contained_by=NumericRange(None, value))
