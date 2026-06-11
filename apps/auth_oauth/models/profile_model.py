from django.contrib.postgres.fields import ArrayField
from django.db import models, transaction
from rest_framework.exceptions import ValidationError

from apps.auth_oauth.constants.auth_constants import GenderChoices
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.utils.utils import calculate_duration_years
from apps.base.models.abstract_base_model import AbstractBaseModel
from apps.base.models.company_model import Company
from apps.base.models.geo_area_model import GeoArea
from apps.base.models.soft_delete_model import SoftDeleteModel


class Profile(AbstractBaseModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="profile_user",
        null=True,
        blank=True,
    )
    profile_picture_id = models.CharField(max_length=36, blank=True, null=True)
    cover_picture_id = models.CharField(max_length=36, blank=True, null=True)
    first_name = models.CharField(max_length=255, null=True, blank=True)
    last_name = models.CharField(max_length=255, null=True, blank=True)
    full_name = models.TextField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=GenderChoices.choices,
        blank=True,
        default=""
    )
    date_of_birth = models.CharField(max_length=255, null=True, blank=True)
    phone_number = models.CharField(max_length=255, null=True, blank=True)
    email = models.CharField(max_length=255, null=True, blank=True)
    location = models.ForeignKey(
        GeoArea,
        on_delete=models.CASCADE,
        related_name="profile_location",
        null=True,
        blank=True,
    )
    location_name = models.CharField(max_length=255, null=True, blank=True)
    linkedin_profile = models.CharField(max_length=255, null=True, blank=True)
    website = models.CharField(max_length=255, null=True, blank=True)
    current_position = models.CharField(max_length=255, null=True, blank=True)
    current_address = models.TextField(null=True, blank=True)
    nationality = models.CharField(null=True, blank=True)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="profile_company",
        null=True,
        blank=True,
    )
    job_preference = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=False)
    submitted_date = models.DateTimeField(null=True, blank=True)
    approval_reason = models.TextField(null=True, blank=True)
    profile_type = models.CharField(null=True, blank=True)
    about_me = models.TextField(null=True, blank=True)
    request_type = models.CharField(max_length=100, null=True, blank=True)
    skills = ArrayField(models.CharField(max_length=255), blank=True, default=list)
    department = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        db_table = "profile"
        description = "Profile"

    @property
    def total_experience_years(self):
        total_years = 0
        # Iterate over related WorkExperience objects
        for exp in self.work_experience_user_profile.all():
            total_years += calculate_duration_years(exp.start_date, exp.end_date)
        return round(total_years, 1) # Return total years rounded to one decimal
    
class ProfileDocumentQuerySet(models.QuerySet):
    """custom queryset for ProfileDocumentModel"""

    def active(self):
        return self.filter(status=ProfileDocumentModel.Status.ACTIVE, is_deleted=False)

    def defaults(self, document_type: str = None):
        qs = self.filter(is_default=True, is_deleted=False)
        if document_type:
            qs = qs.filter(document_type=document_type)
        return qs

    def for_profile(self, profile: Profile, document_type: str = None):
        qs = self.filter(profile=profile, is_deleted=False)
        if document_type:
            qs = qs.filter(document_type=document_type)
        return qs


class ProfileDocumentManager(models.Manager):
    """custom manager for ProfileDocumentModel"""

    def get_queryset(self):
        return ProfileDocumentQuerySet(self.model, using=self._db)

    def active(self):
        return self.get_queryset().active()

    def defaults(self, document_type: str = None):
        return self.get_queryset().defaults(document_type=document_type)

    def for_profile(self, profile: Profile, document_type: str = None):
        return self.get_queryset().for_profile(profile, document_type=document_type)


class ProfileDocumentModel(AbstractBaseModel, SoftDeleteModel):
    """
    Stores documents (e.g., resumes, certificates) linked to a user profile.
    Each profile can only have one default document per document_type.
    """

    class DocumentType(models.TextChoices):
        COVER_LETTER = "cover_letter", "CoverLetter"
        CV = "cv", "CV"
        CERTIFICATE = "certificate", "Certificate"
        PORTFOLIO = "portfolio", "Portfolio"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        DELETED = "DELETED", "Deleted"

    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
        help_text="Profile that owns this document.",
    )
    document_id = models.UUIDField(editable=False, null=True, blank=True, unique=True)
    document_type = models.CharField(
        max_length=255,
        choices=DocumentType.choices,
        null=False,
        blank=False,
        help_text="Type of document (e.g., Cover Letter, CV, Certificate).",
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Marks this document as the default (e.g., main CV).",
    )
    status = models.CharField(
        max_length=50,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Current status of the document.",
    )

    objects = ProfileDocumentManager()

    class Meta:
        db_table = "profile_document"
        verbose_name = "Profile Document"
        verbose_name_plural = "Profile Documents"
        ordering = ["-create_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "document_type"],
                condition=models.Q(is_default=True, is_deleted=False),
                name="unique_default_doc_per_type",
            )
        ]

    def clean(self):
        """
        Ensure only one default document exists per profile and document_type.
        """
        if self.is_default and self.profile and self.document_type:
            qs = ProfileDocumentModel.objects.filter(
                profile=self.profile,
                document_type=self.document_type,
                is_default=True,
                is_deleted=False,
            ).exclude(pk=self.pk)

            if qs.exists():
                raise ValidationError(
                    {"is_default": "Only one default document is allowed per profile and document type."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()  # enforce clean() before save
        return super().save(*args, **kwargs)

    @classmethod
    def set_as_default(cls, profile: Profile, document_id: int, document_type: str):
        """
        Helper method to mark one document as default for a given profile + type.
        Automatically unsets any previous default.
        """
        with transaction.atomic():
            # unset previous defaults
            cls.objects.filter(
                profile=profile,
                document_type=document_type,
                is_default=True,
                is_deleted=False,
            ).update(is_default=False)

            # set new default
            doc = cls.objects.get(pk=document_id, profile=profile, document_type=document_type, is_deleted=False)
            doc.is_default = True
            doc.save()
            return doc

    def __str__(self):
        return f"{self.profile} - {self.document_type or 'Document'} ({self.get_status_display()})"
