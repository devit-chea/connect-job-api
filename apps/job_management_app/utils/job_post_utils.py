import json
from datetime import datetime
from django.utils import timezone
from django_redis import get_redis_connection

from apps.job_management_app.constants.job_application_types import JobApplicationStatus
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_post_model import JobPostModel


def push_to_dead_letter(job_post_id: int, error_message: str):
    redis_client = get_redis_connection("default")
    redis_client.rpush(
        "es_sync_dlq",
        json.dumps(
            {
                "job_post_id": job_post_id,
                "error_message": error_message,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        ),
    )


def get_is_reapplicable(job_post: JobPostModel, request) -> bool:
    now = timezone.now().date()

    # Job-level restrictions
    if not job_post.is_active:
        return False

    if job_post.status in [
        JobPostStatusTypes.CLOSED,
        JobPostStatusTypes.INACTIVE,
        JobPostStatusTypes.SCHEDULED,
    ]:
        return False

    if job_post.expire_date is not None and job_post.expire_date < now:
        return False

    # User-level restrictions
    if not request or not request.user or not request.user.is_authenticated:
        return False

    # Check UCP ID
    user_company_profile_id = getattr(request, "user_company_profile_id", None)
    is_applied = JobApplicationModel.objects.filter(
        create_uid=request.user.id,
        create_ucp_id=user_company_profile_id,
        job_post_id=job_post.id,
        status=JobApplicationStatus.ACTIVE,
    ).exists()
    if not is_applied:
        return False
    
    return True
