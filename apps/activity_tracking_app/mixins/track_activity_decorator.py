import logging
from functools import wraps

from apps.activity_tracking_app.constants.job_activity_types import (
    ActivityTrackingTypes,
)
from apps.activity_tracking_app.services.activity_tracking_services import (
    ActivityTrackingServices,
)

logger = logging.getLogger(__name__)


def track_activity_job_post(func_or_type=None):
    """
    Decorator to track activity for job post, works both with and without arguments.
    @track_activity_job_post(activity_type=ActivityTrackingTypes.VIEW.value)
    @track_activity_job_post
    """

    def decorator(func, activity_type=ActivityTrackingTypes.VIEW.value):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            response = func(self, request, *args, **kwargs)
            instance = self.get_object()
            try:
                ActivityTrackingServices.handle_activity(
                    request=request,
                    job_post_id=instance.id,
                    activity_type=activity_type,
                )
            except Exception as e:
                logger.warning(
                    f"[ActivityTracker] Failed to track activity '{activity_type}' "
                    f"for job_id={getattr(instance, 'id', 'N/A')} | user={request.user}: {e}",
                    exc_info=True,
                )
            return response

        return wrapper

    if callable(func_or_type):
        # Used as @track_activity_job_post
        return decorator(func_or_type)
    else:
        # Used as @track_activity_job_post("view")
        return lambda func: decorator(
            func, func_or_type or ActivityTrackingTypes.VIEW.value
        )
