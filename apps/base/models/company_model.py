from django.db import models

from apps.base.constants.base_constants import CompanyStatusChoices, EntryTypeChoices
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.geo_area_model import GeoArea
from apps.base.models.country_model import Country


class AccessType(models.TextChoices):
    INTERNAL = "internal", "Internal Access"
    EXTERNAL = "external", "External Access"


class Company(AbstractBaseModel):
    profile_picture_id = models.CharField(max_length=255, blank=True, null=True)
    cover_picture_id = models.CharField(max_length=255, blank=True, null=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="company_parent",
    )
    name = models.CharField(max_length=255)
    email = models.CharField(max_length=255, blank=True, null=True)
    website = models.CharField(max_length=255, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    phone_number = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    city = models.ForeignKey(
        GeoArea,
        on_delete=models.CASCADE,
        related_name="company_city",
        blank=True,
        null=True,
    )
    city_name = models.CharField(max_length=255, blank=True, null=True)
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="company_country",
        blank=True,
        null=True,
    )
    email_mask = models.CharField(max_length=255, blank=True, null=True)
    phone_mask = models.CharField(max_length=255, blank=True, null=True)
    logo_description = models.CharField(max_length=255, blank=True, null=True)
    found_date = models.CharField(max_length=255, blank=True, null=True)
    industry = models.CharField(blank=True, null=True)
    postal_code = models.CharField(max_length=255, blank=True, null=True)
    linkedin_email = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(
        max_length=20,
        choices=CompanyStatusChoices.choices,
        null=True,
        default=CompanyStatusChoices.DRAFT.value,
    )
    is_existed = models.BooleanField(default=False)
    about_me = models.TextField(null=True, blank=True)
    assign_admins = models.ManyToManyField(
        "auth_oauth.user",
        related_name="company_assign_admins",
        blank=True,
    )
    company_size = models.CharField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_agree_policy = models.BooleanField(default=False)
    code = models.CharField(null=True, blank=True)
    existed_company = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="company_existed_company",
    )
    access_type = models.CharField(
        max_length=255,
        choices=AccessType.choices,
        default=AccessType.INTERNAL,
        help_text="Access Type Configuration",
    )
    entry_type = models.CharField(
        max_length=20,
        choices=EntryTypeChoices.choices,
        null=True,
        default=EntryTypeChoices.DEFAULT.value,
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Geographic latitude (precision: 6 decimal places)",
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        blank=True,
        null=True,
        help_text="Geographic longitude (precision: 6 decimal places)",
    )
    # for partner integration domain
    is_integrate = models.BooleanField(default=False)
    integrate_domain = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "company"
        description = "Company"
