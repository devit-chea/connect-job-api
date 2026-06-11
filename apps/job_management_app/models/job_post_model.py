from django.contrib.postgres.fields import DecimalRangeField
from django.db import models

from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.abstract_model import AbstractBaseCompany
from apps.base.models.soft_delete_model import SoftDeleteModel
from apps.base.models.sys_value_model import SysValue
from apps.job_management_app.constants.job_post_types import (
    JobPostPrivacyTypes,
    JobPostStatusTypes,
    JobPostPriorityTypes,
    JobPostSalaryTypes,
    JobPostSalaryCurrencyTypes,
)
from apps.job_management_app.models.job_category_model import JobCategoryModel
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
)
from apps.base.models.geo_area_model import GeoArea


class JobPostModel(AbstractBaseModel, SoftDeleteModel, AbstractBaseCompany):
    title = models.CharField(max_length=100, null=True, blank=True)
    tenant_code = models.CharField(max_length=50, null=True, blank=True)
    job_code = models.CharField(max_length=50, null=True, blank=True)
    location = models.CharField(max_length=50, null=True, blank=True)
    post_date = models.DateTimeField(null=True, blank=True)
    expire_date = models.DateField(null=True, blank=True)
    time_type = models.CharField(max_length=50, null=True, blank=True)
    remote_type = models.CharField(max_length=50, null=True, blank=True)
    privacy_type = models.CharField(
        max_length=50,
        choices=JobPostPrivacyTypes.choices,
        default=JobPostPrivacyTypes.PUBLIC,
        null=True,
        blank=True,
    )
    contract_type = models.CharField(max_length=50, null=True, blank=True)
    job_responsibility = models.TextField(null=True, blank=True)
    benefits = models.TextField(null=True, blank=True)
    job_requirement = models.TextField(null=True, blank=True)
    job_description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        choices=JobPostStatusTypes.choices,
        default=JobPostStatusTypes.ACTIVE,
    )
    category = models.CharField(max_length=50, null=True, blank=True)
    priority = models.CharField(
        max_length=50, null=True, blank=True, choices=JobPostPriorityTypes.choices
    )
    salary_type = models.CharField(
        max_length=50, null=True, blank=True, choices=JobPostSalaryTypes.choices
    )
    salary_range = DecimalRangeField(null=True, blank=True)
    salary_currency = models.CharField(
        max_length=5, null=True, blank=True, choices=JobPostSalaryCurrencyTypes.choices
    )
    job_level = models.CharField(max_length=50, null=True, blank=True)
    hire_no = models.IntegerField(null=True, blank=True, default=0)
    job_pipeline_config = models.ForeignKey(
        JobPipelineConfigModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="job_posts",
        help_text="The job pipeline configuration associated with this job post one to one.",
    )
    job_pipeline_step = models.TextField(null=True, blank=True)
    job_location = models.ForeignKey(
        GeoArea,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="job_posts",
    )
    job_category = models.ForeignKey(
        JobCategoryModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="job_posts",
    )
    year_of_experience = models.CharField(max_length=50, blank=True, default="")
    is_pipeline_visible = models.BooleanField(
        default=False,
        help_text="To decide whether applicants can see the pipeline when create a job post",
    )
    # Lineage tracking
    reposted_from = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reposts",
    )
    reposted_at = models.DateTimeField(null=True, blank=True)
    assigned_recruiters = models.ManyToManyField(
        "auth_oauth.UserCompanyProfile",
        through="job_management_app.JobPostAssignedRecruiterModel",
        through_fields=("job_post", "assigned_ucp"),
        related_name="+",
        blank=True,
    )

    class Meta:
        db_table = "job_post"
        description = "Job Posting Model"
