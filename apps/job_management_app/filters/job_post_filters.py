import django_filters
from django_filters import CharFilter, NumberFilter, BaseInFilter

from apps.job_management_app.models.job_post_model import JobPostModel


class CharInFilter(BaseInFilter, CharFilter):
    """Accepts comma-separated string values: ?timeType=Full-Time,Part-Time"""

    pass


class JobPostByCompanyFilter(django_filters.FilterSet):
    # Single value filter
    location = CharFilter(field_name="location", lookup_expr="iexact")

    # Multi-value dynamic string filters (comma-separated)
    timeType = CharInFilter(field_name="time_type", lookup_expr="in")
    remoteType = CharInFilter(field_name="remote_type", lookup_expr="in")
    jobLevel = CharInFilter(field_name="job_level", lookup_expr="in")
    categories = CharInFilter(field_name="category", lookup_expr="in")

    # Salary range filters against DecimalRangeField
    salaryMin = NumberFilter(field_name="salary_range", method="filter_salary_min")
    salaryMax = NumberFilter(field_name="salary_range", method="filter_salary_max")
    salaryCurrency = CharFilter(field_name="salary_currency", lookup_expr="iexact")

    def filter_salary_min(self, queryset, name, value):
        """
        Keep jobs where the range's lower bound >= salaryMin
        e.g. ?salaryMin=500 → salary_range lower bound must be >= 500
        """
        return queryset.filter(salary_range__startswith__gte=value)

    def filter_salary_max(self, queryset, name, value):
        """
        Keep jobs where the range's upper bound <= salaryMax
        e.g. ?salaryMax=1000 → salary_range upper bound must be <= 1000
        """
        return queryset.filter(salary_range__endswith__lte=value)

    class Meta:
        model = JobPostModel
        fields = [
            "location",
            "timeType",
            "remoteType",
            "jobLevel",
            "category",
            "salaryMin",
            "salaryMax",
            "salaryCurrency",
        ]
