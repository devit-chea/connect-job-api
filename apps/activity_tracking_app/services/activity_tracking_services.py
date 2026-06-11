import logging

import redis
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from django_redis import get_redis_connection

from apps.activity_tracking_app.constants.job_activity_types import (
    ActivityTrackingTypes,
)
from apps.activity_tracking_app.models.job_post_user_activity_count_model import (
    JobPostUserActivityCountModel,
)
from apps.activity_tracking_app.models.job_post_user_event_model import (
    JobPostUserEventModel,
)
from apps.activity_tracking_app.models.job_post_user_state_model import (
    JobPostUserStateModel,
)
from apps.activity_tracking_app.services.job_activity_services import ACTIVITY_TRACKING_MAP
from apps.activity_tracking_app.tasks.tasks import (
    increment_activity_in_redis,
    ACTIVITY_TTL_MAP,
    ACTIVITY_TRACKING_TASK_MAP,
)
from apps.activity_tracking_app.utils.redis_key_formatters import (
    dedup_key_user,
    dedup_key_anon,
    redis_counter_key,
)
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
from apps.base.utils.base_util import get_client_ip
from apps.core.exceptions.base_exceptions import NotFoundException
from apps.job_management_app.models.job_post_model import JobPostModel

logger = logging.getLogger(__name__)


class ActivityTrackingServices:

    @staticmethod
    def handle_activity(request, job_post_id: int, activity_type: str):
        """
        Handles job post activity for both authenticated and anonymous users.
        """

        if activity_type not in ActivityTrackingTypes.values:
            raise ValidationError(f"Invalid activity type: {activity_type}")

        is_anonymous = not request.user.is_authenticated
        if is_anonymous and activity_type != ActivityTrackingTypes.VIEW:
            raise PermissionDenied("Anonymous users may only perform 'view' activity.")

        user_company_profile_id = request.user_company_profile_id
        anonymous_id = get_client_ip(request) if is_anonymous else None
        user_agent = request.headers.get("User-Agent")

        # Handle activity view/save/unsave/apply
        if activity_type != ActivityTrackingTypes.VIEW.value:
            task = ACTIVITY_TRACKING_MAP.get(activity_type)  # Use ACTIVITY_TRACKING_MAP
            if not task:
                logger.error(f"Error: Invalid activity type [{activity_type}]")
                raise ValueError(f"Invalid activity type: {activity_type}")
            task(user_company_profile_id, job_post_id)
            
        # TODO: Will remove soon  
        # if activity_type != ActivityTrackingTypes.VIEW.value:
        #     task = ACTIVITY_TRACKING_TASK_MAP.get(activity_type)
        #     if not task:
        #         logger.error(f"Error: Invalid activity type [{activity_type}]")
        #         raise ValueError(f"Invalid activity type: {activity_type}")
        #     task.delay(user_company_profile_id, job_post_id)
        else:
            task_args = dict(
                job_post_id=job_post_id,
                activity_type=activity_type,
                user_company_profile_id=user_company_profile_id,
                is_anonymous=is_anonymous,
                anonymous_id=anonymous_id or "unknown",
                user_agent=user_agent,
            )

            increment_activity_in_redis.apply_async(kwargs=task_args)
            
    
    @staticmethod
    def increment(
        job_post_id,
        activity_type,
        user_company_profile_id=None,
        is_anonymous=False,
        anonymous_id=None,
        user_agent=None,
    ):
        if activity_type not in ActivityTrackingTypes.values:
            raise ValueError(f"Invalid activity type: {activity_type}")

        # CONDITION: ACCEPT ONLY VIEW ACTIVITY, IF NOT RETURN
        # SAVE/UNSAVE AND APPLY ARE HAVE BEEN MOVE TO COUNT REALTIME WITH TASKS
        if activity_type != ActivityTrackingTypes.VIEW.value:
            return

        dedup_key = None
        if user_company_profile_id:
            dedup_key = dedup_key_user(
                user_company_profile_id, activity_type, job_post_id
            )
        elif is_anonymous and anonymous_id:
            dedup_key = dedup_key_anon(anonymous_id, activity_type, job_post_id)

        counter_key = redis_counter_key(activity_type, job_post_id)
        
        con = get_redis_connection("default",) 
        pipeline = con.pipeline()

        try:
            # Handle dedup key
            if dedup_key:
                if con.exists(dedup_key):
                    return
                ttl = ACTIVITY_TTL_MAP.get(activity_type)
                if ttl:
                    pipeline.setex(dedup_key, ttl, 1)
                else:
                    pipeline.set(dedup_key, 1)
                pipeline.sadd("job_activity_dedup_keys", dedup_key)

            # Count activity
            pipeline.incr(counter_key)
            pipeline.sadd("job_activity_keys", counter_key)

            pipeline.execute()
        except redis.exceptions.RedisError as e:
            logger.error(f"[ActivityTracker] Redis error for job {job_post_id=} {activity_type=}: {e}")
            raise

    @staticmethod
    def decrease_saved(job_post_id, user_company_profile_id):
        """
        Decrement save count for a job post and remove dedup keys from Redis.
        """
        dedup_key = f"user:{user_company_profile_id}:save:{job_post_id}"
        counter_key = f"job_activity:save:{job_post_id}"

        try:
            con = get_redis_connection("default",) 
            pipeline = con.pipeline()
            
            if con.exists(dedup_key):
                pipeline.delete(dedup_key)
                pipeline.srem("job_activity_dedup_keys", dedup_key)

                current_value = con.get(counter_key)
                try:
                    new_value = max(0, int(current_value or 0) - 1)
                except ValueError:
                    logger.error(
                        f"Invalid save count for {counter_key}, resetting to 0"
                    )
                    new_value = 0

                pipeline.set(counter_key, new_value)

            pipeline.execute()
        except redis.exceptions.RedisError as e:
            logger.error(
                f"[ActivityTracker] Redis error while decrementing save count "
                f"for job_id={job_post_id}, user={user_company_profile_id}: {e}"
            )
            raise


def create_user_event(user_company_profile, job_post, activity_type):
    try:
        JobPostUserEventModel.objects.create(
            user_company_profile=user_company_profile,
            job_post=job_post,
            activity_type=activity_type,
        )
    except Exception as e:
        logger.error(f"Failed to log event for user: {e}")


@transaction.atomic
def save_job_post(user_company_profile_id, job_post_id):
    try:
        logger.info(f"Handling save for job post {job_post_id}")
        user_company_profile = UserCompanyProfile.objects.get(
            id=user_company_profile_id
        )
    except UserCompanyProfile.DoesNotExist:
        raise NotFoundException(
            f"UserCompanyProfile with id {user_company_profile_id} does not exist."
        )

    try:
        job_post = JobPostModel.objects.get(id=job_post_id)
    except JobPostModel.DoesNotExist:
        raise NotFoundException(f"JobPostModel with id {job_post_id} does not exist.")

    create_user_event(user_company_profile, job_post, ActivityTrackingTypes.SAVE.value)

    state, created = JobPostUserStateModel.objects.select_for_update().get_or_create(
        user_company_profile=user_company_profile,
        job_post=job_post,
        defaults={
            "is_saved": True,
            "save_at": timezone.now(),
            "status": "saved",
        },
    )

    if not created and not state.is_saved:
        state.is_saved = True
        state.save_at = timezone.now()
        state.save()

    count_obj, _ = JobPostUserActivityCountModel.objects.get_or_create(
        job_post=job_post
    )
    count_obj.save_count = F("save_count") + 1
    count_obj.save()


@transaction.atomic
def unsave_job_post(user_company_profile_id, job_post_id):
    try:
        logger.info(f"Handling unsave for job post {job_post_id}")
        user_company_profile = UserCompanyProfile.objects.get(
            id=user_company_profile_id
        )
    except UserCompanyProfile.DoesNotExist:
        raise NotFoundException(
            f"UserCompanyProfile with id {user_company_profile_id} does not exist."
        )

    try:
        job_post = JobPostModel.objects.get(id=job_post_id)
    except JobPostModel.DoesNotExist:
        raise NotFoundException(f"JobPostModel with id {job_post_id} does not exist.")

    create_user_event(
        user_company_profile, job_post, ActivityTrackingTypes.UNSAVE.value
    )

    try:
        state = JobPostUserStateModel.objects.select_for_update().get(
            user_company_profile=user_company_profile,
            job_post=job_post,
        )
    except JobPostUserStateModel.DoesNotExist:
        return

    if state.is_saved:
        state.is_saved = False
        # Optionally update status if you want
        state.save()

        count_obj, _ = JobPostUserActivityCountModel.objects.get_or_create(
            job_post=job_post
        )
        if count_obj.save_count > 0:
            count_obj.save_count = F("save_count") - 1
            count_obj.save()


@transaction.atomic
def apply_job_post(user_company_profile_id, job_post_id):
    try:
        logger.info(f"Handling apply for job post {job_post_id}")
        user_company_profile = UserCompanyProfile.objects.get(
            id=user_company_profile_id
        )
    except UserCompanyProfile.DoesNotExist:
        raise NotFoundException(
            f"UserCompanyProfile with id {user_company_profile_id} does not exist."
        )

    try:
        job_post = JobPostModel.objects.get(id=job_post_id)
    except JobPostModel.DoesNotExist:
        raise NotFoundException(f"JobPostModel with id {job_post_id} does not exist.")

    create_user_event(user_company_profile, job_post, ActivityTrackingTypes.APPLY.value)

    now = timezone.now()
    
    state, created = JobPostUserStateModel.objects.select_for_update().get_or_create(
        user_company_profile=user_company_profile,
        job_post=job_post,
        defaults={
            "applied_at": now,
            "status": "applied",
        },
    )

    if not created and state.status != "applied":
        # was_saved = state.is_saved
        state.status = "applied"
        state.applied_at = now
        state.save()

    count_obj, _ = JobPostUserActivityCountModel.objects.get_or_create(
        job_post=job_post
    )
    count_obj.apply_count = F("apply_count") + 1

    # TODO: Uncomment this when required minusz  save count while applying
    # if was_saved and count_obj.save_count > 0:
    #     count_obj.save_count = F('save_count') - 1

    count_obj.save()