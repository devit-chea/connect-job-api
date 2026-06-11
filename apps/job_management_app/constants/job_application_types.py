from django.db import models


class JobApplicationStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    DELETED = "DELETED", "Deleted"


class JobApplicationStateTypes(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


QUESTION_TYPE_CHOICES = (
    ("text", "Text"),
    ("single_choice", "Single Choice"),
    ("multi_choice", "Multi Choice"),
)


class ResumeFileTypes(models.TextChoices):
    DOC = "DOC", "DOC"
    PDF = "PDF", "PDF"
    ZIP = "ZIP", "ZIP"
    JPG = "JPG", "JPG"
    PNG = "PNG", "PNG"


class EmploymentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    REJECT = "REJECT", "Reject"
    RESIGN = "RESIGN", "Resign"
    TO_BE_STARTED = "TO_BE_STARTED", "To Be Started"
