import logging
from apps.activity_tracking_app.constants.job_activity_types import (
    ActivityTrackingTypes,
)

logger = logging.getLogger(__name__)


def sync_save_job_post(user_company_profile_id, job_post_id):
    try:
        from apps.activity_tracking_app.services.activity_tracking_services import (
            save_job_post,
        )

        save_job_post(user_company_profile_id, job_post_id)
    except Exception as exc:
        logger.exception(exc)


def sync_unsave_job_post(user_company_profile_id, job_post_id):
    try:
        from apps.activity_tracking_app.services.activity_tracking_services import (
            unsave_job_post,
        )

        unsave_job_post(user_company_profile_id, job_post_id)
    except Exception as exc:
        logger.exception(exc)


def sync_apply_job_post(user_company_profile_id, job_post_id):
    try:
        from apps.activity_tracking_app.services.activity_tracking_services import (
            apply_job_post,
        )

        apply_job_post(user_company_profile_id, job_post_id)
    except Exception as exc:
        logger.exception(exc)


ACTIVITY_TRACKING_MAP = {
    ActivityTrackingTypes.SAVE.value: sync_save_job_post,
    ActivityTrackingTypes.UNSAVE.value: sync_unsave_job_post,
    ActivityTrackingTypes.APPLY.value: sync_apply_job_post,
}
