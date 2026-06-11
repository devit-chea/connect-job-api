class WorkforcePlanningResource:
    MINIMUM = "minimum"
    AVERAGE = "average"
    MAXIMUM = "maximum"


class WorkforcePlanning:
    RESOURCE_PLANNING = "ResourcePlanning"
    DEPARTMENT_PLANNING = "DepartmentPlanning"


class Status:
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending approval"
    DRAFT = "draft"
    CANCELED = "canceled"
    DELETED = "deleted"
    ADJUSTED = "adjusted"
    REVISED = "revised"
    SHARED = "shared"


class RequestType:
    NORMAL = "normal"
    CANCEL = "cancel"
    ADJUSTMENT = "adjustment"
    SHARE = "share"
    MINIMUM = "minimum"
    AVERAGE = "average"
    MAXIMUM = "maximum"


class ApplicantStatus:
    ACTIVE = "active"
    BLACKLIST = "blacklist"


class HiringStatus:
    NEW_HIRE = "new_hired"
    RE_HIRE = "re_hired"


class JobOfferRemarkType:
    REJECT_OFFER = "reject_offer"
    CANCEL_OFFER = "cancel_offer"


class RecruitmentJobAppliedSearchField:
    RECRUITMENT_JOB_APPLIED = [
        "job_code__position__name",
        "job_code__job_type__name",
        "status",
        "start_date",
        "end_date",
        "job_vacancies__code",
        "rar_number__request_number",
    ]


class RecruitmentJobAppliedLookUpField:
    RECRUITMENT_JOB_APPLIED = [
        "id",
        "job_code__position__name",
        "job_vacancies__code",
    ]


class JobOfferContractState:
    CANCELED = "Canceled Offer"
    COMPLETED = "Completed"
    RE_SUBMITTED = "Re-Submitted"
    NOT_STARTED = "Not Started"
    CLOSED = "Closed"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class JobOfferContractCandidateState:
    REJECTED = "Candidate Rejected"
    SUBMITTED = "Submitted"
    SAVED = "Candidate In Review"


class CommunicateKeys:
    NOTIFY = "notify"
    CREATE = "create"
    UPDATE_PHONE_NUMBER = "update phone number"
    UPDATE_CLOSE_STATE = "update close state"
    UPDATE_CANCEL_STATE = "update cancel state"
    UPDATE_REJECT_STATE = "update reject state"
