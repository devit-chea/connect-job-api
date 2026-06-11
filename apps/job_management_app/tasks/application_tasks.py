import logging
from celery import shared_task
from django.db import transaction

from apps.auth_oauth.models.profile_model import Profile
from apps.elasticsearch_app.services.applicant_recommend_service import (
    get_applicant_score,
)
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_post_model import JobPostModel


logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name="elastic_task.calculate_and_update_score",
    max_retries=3,
    default_retry_delay=60,  # 1 min
    acks_late=True,
)
def calculate_and_update_score(self, **kwargs):
    """
    Background task to calculate a single applicant's score against a job post
    and update the corresponding JobApplicationModel instance.
    """
    job_post_pk = kwargs.get("job_post_pk")
    profile_pk = kwargs.get("profile_pk")
    application_pk = kwargs.get("application_pk")
    
    try:
        job_post = JobPostModel.objects.get(pk=job_post_pk)
        application = JobApplicationModel.objects.get(pk=application_pk)

    except (
        JobPostModel.DoesNotExist,
        JobApplicationModel.DoesNotExist,
        Profile.DoesNotExist,
    ) as e:
        print(f"Required object not found for scoring: {e}")
        return False

    raw_score = get_applicant_score(job_post=job_post, profile_id=profile_pk)

    try:
        with transaction.atomic():
            application.score = raw_score
            application.save(update_fields=["score"])

        return True

    except Exception as e:
        # Handle database errors or other exceptions during save
        logger(f"Error updating score for application {application_pk}: {e}")
        return False
