from django.db import models


class JobPostStatusTypes(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    INACTIVE = "INACTIVE", "Inactive"
    DELETED = "DELETED", "Deleted"
    DRAFT = "DRAFT", "Draft"
    CLOSED = "CLOSED", "Closed"
    PUBLISHED = "PUBLISHED", "Published"
    SCHEDULED = "SCHEDULED", "Scheduled"


class JobPostPrivacyTypes(models.TextChoices):
    PUBLIC = "PUBLIC", "Public"
    INTERNAL = "INTERNAL", "Internal"
    ONLY_ME = "ONLY_ME", "Only Me"


class JobPostPriorityTypes(models.TextChoices):
    URGENT = "URGENT", "Urgent"
    HIGH = "HIGH", "High"
    MEDIUM = "MEDIUM", "Medium"
    LOW = "LOW", "Low"


class JobPostSalaryTypes(models.TextChoices):
    FIXED = "FIXED", "Fixed"
    RANGE = "RANGE", "Range"
    NEGOTIABLE = "NEGOTIABLE", "Negotiable"


class JobPostSalaryCurrencyTypes(models.TextChoices):
    KHR = "KHR", "KHR"
    USD = "USD", "USD"
    THB = "THB", "THB"
