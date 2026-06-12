import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="integration.sync_pipeline_to_erp",
    max_retries=3,
    default_retry_delay=60,
)
def sync_pipeline_to_erp(self, application_id: int) -> None:
    """
    Async Celery task: push a pipeline step/status change to the connected ERP.

    Dispatched via transaction.on_commit() from update_pipeline() so it only
    fires after the DB transaction has committed successfully.
    """
    from apps.job_management_app.models.job_application_model import JobApplicationModel
    from apps.integration.services.pipeline_sync_service import PipelineSyncService

    application = (
        JobApplicationModel.objects
        .select_related("job_post", "profile")
        .filter(id=application_id)
        .first()
    )

    if not application:
        logger.warning(
            "sync_pipeline_to_erp: application_id=%s not found — task aborted",
            application_id,
        )
        return

    try:
        PipelineSyncService.sync_to_erp(application)
    except Exception as exc:
        logger.warning(
            "sync_pipeline_to_erp: attempt %d/%d failed application_id=%s error=%s",
            self.request.retries + 1,
            self.max_retries + 1,
            application_id,
            exc,
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                "sync_pipeline_to_erp: all retries exhausted application_id=%s",
                application_id,
            )


@shared_task(
    bind=True,
    name="integration.sync_recruiter_to_erp",
    max_retries=3,
    default_retry_delay=60,
)
def sync_recruiter_to_erp(self, ucp_id: int) -> None:
    """
    Async Celery task: push a newly created recruiter/admin user to the ERP
    and store the IntegrationUserMapping for cross-system reference.

    The mapping record with partner_user_id=None is already written by the
    signal before this task runs, so the reference always exists locally.
    """
    from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
    from apps.integration.services.recruiter_sync_service import RecruiterSyncService

    ucp = (
        UserCompanyProfile.objects
        .select_related("user", "profile", "company")
        .filter(id=ucp_id)
        .first()
    )

    if not ucp:
        logger.warning(
            "sync_recruiter_to_erp: ucp_id=%s not found — task aborted", ucp_id
        )
        return

    try:
        RecruiterSyncService.sync_to_erp(ucp)
    except Exception as exc:
        logger.warning(
            "sync_recruiter_to_erp: attempt %d/%d failed ucp_id=%s error=%s",
            self.request.retries + 1,
            self.max_retries + 1,
            ucp_id,
            exc,
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                "sync_recruiter_to_erp: all retries exhausted ucp_id=%s", ucp_id
            )


@shared_task(
    bind=True,
    name="integration.sync_applicant_to_erp",
    max_retries=3,
    default_retry_delay=60,   # 1 minute between retries
)
def sync_applicant_to_erp(self, application_id: int) -> None:
    """
    Async Celery task: push a new job application to the connected ERP.

    Retried up to 3 times (at 1 min intervals) if the ERP is temporarily
    unavailable. Permanent failures are logged and swallowed after the last
    retry so the applicant's experience on ConnectJob is never affected.
    """
    from apps.job_management_app.models.job_application_model import JobApplicationModel
    from apps.integration.services.applicant_sync_service import ApplicantSyncService

    application = (
        JobApplicationModel.objects
        .select_related("job_post", "profile")
        .filter(id=application_id)
        .first()
    )

    if not application:
        logger.warning(
            "sync_applicant_to_erp: application_id=%s not found — task aborted",
            application_id,
        )
        return

    try:
        ApplicantSyncService.sync_to_erp(application)
    except Exception as exc:
        logger.warning(
            "sync_applicant_to_erp: attempt %d/%d failed application_id=%s error=%s",
            self.request.retries + 1,
            self.max_retries + 1,
            application_id,
            exc,
        )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            logger.error(
                "sync_applicant_to_erp: all retries exhausted application_id=%s",
                application_id,
            )
