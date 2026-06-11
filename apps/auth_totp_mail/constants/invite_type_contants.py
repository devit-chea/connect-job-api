from django.db import models


class TemplateType(models.TextChoices):
    INVITATION = "INVITATION", "Invitation"
    REJECTION = "REJECTION", "Rejection"
    GENERAL = "GENERAL", "General"


class InvitationType(models.TextChoices):
    # Recruiter Invitation Type to Applicant
    INTERVIEW = "invite.interview", "Interview Invite"
    SIGN_CONTRACT = "invite.sign_contract", "Sign Contract Invite"
    OFFER = "invite.offer", "Offer Invite"
    ASSESSMENT = "invite.assessment", "Assessment Invite"


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"
    DONE = "DONE", "Done"


ALLOWED_MANUAL_STATUSES = [
    InvitationStatus.DONE,
    InvitationStatus.CANCELLED,
    InvitationStatus.FAILED,
    InvitationStatus.SENT,
    InvitationStatus.PENDING,
]
