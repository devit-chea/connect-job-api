from rest_framework import serializers

from apps.job_management_app.constants.job_post_types import (
    JobPostPrivacyTypes,
    JobPostPriorityTypes,
    JobPostSalaryCurrencyTypes,
    JobPostSalaryTypes,
    JobPostStatusTypes,
)


class InboundJobPostSerializer(serializers.Serializer):
    """
    Accepts ConnectJob-field-named data produced by transform_erp_payload().
    All fields are optional so a partial ERP payload still creates a valid draft.
    salary_min / salary_max are split fields that the view reassembles into
    the DecimalRangeField expected by JobPostModel.
    """

    # ── Core ──────────────────────────────────────────────────────────────────
    title = serializers.CharField(max_length=100, required=True)
    job_code = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    tenant_code = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    job_description = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    job_requirement = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    job_responsibility = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    benefits = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )

    # ── Classification ────────────────────────────────────────────────────────
    category = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    job_level = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    time_type = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    remote_type = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    contract_type = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )
    privacy_type = serializers.ChoiceField(
        choices=JobPostPrivacyTypes.choices,
        required=False,
        allow_null=True,
        default=JobPostPrivacyTypes.PUBLIC,
    )
    priority = serializers.ChoiceField(
        choices=JobPostPriorityTypes.choices, required=False, allow_null=True
    )
    status = serializers.ChoiceField(
        choices=JobPostStatusTypes.choices,
        required=False,
        allow_null=True,
        default=JobPostStatusTypes.ACTIVE,
    )

    # ── Location ──────────────────────────────────────────────────────────────
    location = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )

    # ── Salary ────────────────────────────────────────────────────────────────
    salary_type = serializers.ChoiceField(
        choices=JobPostSalaryTypes.choices, required=False, allow_null=True
    )
    salary_currency = serializers.ChoiceField(
        choices=JobPostSalaryCurrencyTypes.choices, required=False, allow_null=True
    )
    # Stored separately; the view merges them into DecimalRangeField
    salary_min = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )
    salary_max = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    post_date = serializers.DateTimeField(required=False, allow_null=True)
    expire_date = serializers.DateField(required=False, allow_null=True)

    # ── Headcount ─────────────────────────────────────────────────────────────
    hire_no = serializers.IntegerField(
        required=False, allow_null=True, min_value=0
    )
    year_of_experience = serializers.CharField(
        max_length=50, required=False, allow_null=True, allow_blank=True
    )

    def validate(self, attrs):
        salary_min = attrs.get("salary_min")
        salary_max = attrs.get("salary_max")
        if salary_min is not None and salary_max is not None:
            if salary_min > salary_max:
                raise serializers.ValidationError(
                    {"salary_min": "salary_min must be less than or equal to salary_max."}
                )
        return attrs
