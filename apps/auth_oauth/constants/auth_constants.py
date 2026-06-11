from django.db import models


class UserStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


class UserState:
    PENDING_VERIFY_OPT = "pending_verify_otp"
    COMPLETE_VERIFY_OPT = "complete_verify_otp"
    PENDING_SETUP_PROFILE = "pending_setup_profile"
    COMPLETE_SETUP_PROFILE = "complete_setup_profile"


class UserTypes(models.TextChoices):
    APPLICANT = "applicant", "Applicant"
    RECRUITER = "recruiter", "Recruiter"
    PENDING_ADMIN_RECRUITER = "pending_recruiter", "Pending Recruiter"
    ADMIN_RECRUITER = "admin_recruiter", "Admin Recruiter"
    OPERATOR = "operator", "Operator"
    SUPER_ADMIN = "super_admin", "super_admin"

class AuthenticationProviders(models.TextChoices):
    GOOGLE = "google", "Google"
    LINKEDIN = "linkedin", "Linkedin"
    APPLE = "apple", "Apple"


class RecruiterSetupProfileStep:
    # RSP = recruiter setup profile
    RSP1 = "RSP1"
    RSP2 = "RSP2"
    RSP3 = "RSP3"


class ApplicantBecomeRecruiterStep:
    # ABR = applicant become recruiter
    ABR1 = "ABR1"
    ABR2 = "ABR2"


class ProfileStatus:
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


class ProfileCode:
    OPERATOR = "operator"
    ADMIN_RECRUITER = "admin_recruiter"
    REQUEST_NEW = "request_new"


class RequestType:
    BECOME_RECRUITER = "become_recruiter"
    NEW_COMPANY = "new_company"
    ADDITIONAL_COMPANY = "additional_company"


class LanguageLevels(models.TextChoices):
    BEGINNER = "beginner", "Beginner"
    MEDIUM = "medium", "Medium"
    ADVANCE = "advance", "Advance"


class PermissionTypes(models.TextChoices):
    MENU = "menu", "Menu"
    PERMISSION = "permission", "Permission"


class GroupTypes(models.TextChoices):
    OPERATOR = "operator", "Operator"
    ADMIN_RECRUITER = "admin_recruiter", "Admin Recruiter"
    RECRUITER = "recruiter", "Recruiter"
    APPLICANT = "applicant", "Applicant"


class PermissionOptions(models.TextChoices):
    ALLOWED = "allowed", "Allowed"
    DENIED = "denied", "Denied"
    VIEW_ONLY = "view_only", "View Only"


class DefaultRole:
    OPERATOR_DEFAULT_ROLE = "OPERATOR_DEFAULT_ROLE"
    ADMIN_RECRUITER_ROLE = "ADMIN_RECRUITER_ROLE"
    RECRUITER_ROLE = "RECRUITER_ROLE"
    APPLICANT_ROLE = "APPLICANT_ROLE"
    PENDING_ADMIN_RECRUITER_ROLE = "PENDING_ADMIN_RECRUITER_DEFAULT_ROLE"
    
class GenderChoices(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"