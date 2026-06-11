import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.activity_tracking_app.models.job_post_user_activity_count_model import (
    JobPostUserActivityCountModel,
)
from apps.auth_oauth.models.profile_model import Profile
from apps.base.models.company_model import Company
from apps.elasticsearch_app.services.job_post_es_sync_services import (
    JobPostESSyncServices,
)
from apps.elasticsearch_app.tasks.tasks import (
    bulk_sync_job_post_to_es,
    sync_job_post_to_es,
)
from apps.job_management_app.models.job_post_additional_field_model import (
    JobPostAdditionalFieldModel,
)
from apps.job_management_app.models.job_post_model import JobPostModel

logger = logging.getLogger(__name__)


def _enqueue_es_sync(job_post, fields=None, force_delete=False):
    if not job_post or not getattr(job_post, "id", None):
        logger.error(f"[Signal] JobPost(id={job_post.id}) does not exist in database")
        return
    logger.info(f"[Signal] Enqueueing ES sync for JobPost(id={job_post.id})")
    sync_job_post_to_es.delay(
        job_post_id=job_post.id, fields=fields, force_delete=force_delete
    )


@receiver(post_save, sender=Company)
@receiver(post_delete, sender=Company)
def sync_es_for_company(sender, instance, **kwargs):
    logger.info(f"[ES Sync] Syncing Company(id={instance.id}) to Elasticsearch")
    job_post_ids = list(
        JobPostModel.objects.filter(company_id=instance.pk).values_list("id", flat=True)
    )

    if not job_post_ids:
        logger.info(
            f"[Signal] No job posts found for Company(id={instance.pk}), skipping sync."
        )
        return

    fields = JobPostESSyncServices.get_sync_fields_for_related(instance)
    logger.info(
        f"[Signal] Bulk syncing {len(job_post_ids)} job posts for Company(id={instance.pk})"
    )

    chunk_size = 500
    for i in range(0, len(job_post_ids), chunk_size):
        chunk = job_post_ids[i : i + chunk_size]
        logger.debug(f"[Signal] Enqueueing sync for chunk of {len(chunk)} job posts")

        # Enqueue task using apply_async with kwargs only
        bulk_sync_job_post_to_es.apply_async(
            kwargs={"job_post_ids": chunk, "fields": fields or []}
        )


@receiver(post_save, sender=JobPostAdditionalFieldModel)
@receiver(post_delete, sender=JobPostAdditionalFieldModel)
def sync_es_for_additional_field(sender, instance, **kwargs):
    logger.info(
        f"[ES Sync] Syncing JobPostAdditionalField(id={instance.id}) to Elasticsearch"
    )
    job_post = getattr(instance, "job_post", None)
    fields = JobPostESSyncServices.get_sync_fields_for_related(instance)
    _enqueue_es_sync(job_post, fields=fields)


@receiver(post_save, sender=JobPostUserActivityCountModel)
@receiver(post_delete, sender=JobPostUserActivityCountModel)
def sync_es_for_user_activity_count(sender, instance, **kwargs):
    logger.info(
        f"[ES Sync] Syncing JobPostUserActivityCount(id={instance.id}) to Elasticsearch"
    )
    job_post = getattr(instance, "job_post", None)
    fields = JobPostESSyncServices.get_sync_fields_for_related(instance)
    _enqueue_es_sync(job_post, fields=fields)


@receiver(post_save, sender=JobPostModel)
@receiver(post_delete, sender=JobPostModel)
def sync_es_for_job_post(sender, instance, created=None, **kwargs):
    if created is True:
        return
    logger.info(f"[ES Sync] Syncing JobPost(id={instance.id}) to Elasticsearch")
    _enqueue_es_sync(instance)


@receiver(post_save, sender=Profile)
@receiver(post_delete, sender=Profile)
def sync_es_for_profile(sender, instance, created=None, **kwargs):
    if created is True:
        return
    logger.info(f"[ES Sync] Syncing Profile(id={instance.id}) to Elasticsearch")
    _enqueue_es_sync(instance)
