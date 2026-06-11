from django.db import models

class FileAccessLevel:
    PUBLIC = "public"
    PRIVATE = "private"


class ModelFieldChoices:
    FILE_ACCESS_LEVEL_CHOICES = [
        (FileAccessLevel.PUBLIC, "Public"),
        (FileAccessLevel.PRIVATE, "Private"),
    ]


class ExcludeMetaField:
    @classmethod
    def get_exclude_field(cls):
        return [
            "create_date",
            "create_uid",
            "write_date",
            "write_uid",
        ]


class RefType:
    COMPANY_LOGO = "company_logo"


class Status:
    SUBMITTED = "submitted"
    PENDING = "pending"
    REJECTED = "rejected"
    APPROVED = "approved"
    ACCEPTED = "accepted"
    COMPLETE = "complete"


class ENV:
    DEV = "dev"


class UserAgentType:
    IOS = "ios"
    ANDROID = "android"

class CompanyStatusChoices(models.TextChoices):
    SUBMITTED = "submitted", "Submitted"
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    REJECTED = "rejected", "Rejected"
    COMPLETE = "complete", "Complete"
    APPROVED = "approved", "Approved"
    DRAFT = "draft", "Draft"
    RESUBMITTED = "resubmitted", "Resubmitted"
    
class EntryTypeChoices(models.TextChoices):
    DEFAULT = "default", "Default"
    ADDITIONAL = "additional", "Additional"