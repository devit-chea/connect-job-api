import logging

from django.db.models import QuerySet
from elasticsearch.exceptions import ElasticsearchException, NotFoundError
from typing_extensions import Optional, List

from apps.activity_tracking_app.models.job_post_user_activity_count_model import JobPostUserActivityCountModel
from apps.base.models.company_model import Company
from apps.base.utils.log_utils import log_sync_call_origin
from apps.elasticsearch_app.models.job_post_document import JobPostDocument
from apps.elasticsearch_app.utils.es_utils import build_es_partial_update_doc, \
    partial_update_es_document
from apps.job_management_app.models.job_post_additional_field_model import JobPostAdditionalFieldModel
from apps.job_management_app.models.job_post_model import JobPostModel

logger = logging.getLogger(__name__)


class JobPostESSyncServices:
    RELATED_MODEL_FIELD_MAP = {
        JobPostAdditionalFieldModel: ["additional_field"],
        JobPostUserActivityCountModel: ["view_count", "save_count", "apply_count"],
        Company: ["company"],
        JobPostModel: None,  # None = full update
    }

    @classmethod
    def get_sync_fields_for_related(cls, instance) -> Optional[List[str]]:
        """
        - Get the fields to be synced for a related model.
        :param instance: The related model instance.
        :return: List[str]
        """
        return cls.RELATED_MODEL_FIELD_MAP.get(type(instance), None)

    @classmethod
    @log_sync_call_origin
    def sync(cls, job_post: JobPostModel, fields: Optional[List[str]] = None, force_delete: bool = False) -> None:
        """
        - Sync a single job post to elasticsearch.
        - Main entry point to sync one job post(full or partial) to elasticsearch.
        - If the job post is not found in elasticsearch, it will be created.
        - If the job post is found in elasticsearch, it will be updated.
        - If the job post is found in elasticsearch and force_delete is True, it will be deleted.

        Args:
            job_post (JobPostModel): The job post to be synced to elasticsearch.
            fields (Optional[List[str]]): The fields to be synced to elasticsearch.
            force_delete (bool): Whether to force delete the job post from elasticsearch.

        Returns:
            None
        """

        if getattr(job_post, 'is_deleted', False) or force_delete:
            return cls.sync_delete(job_post.id)

        try:
            doc = JobPostDocument()
            if fields:
                partial_doc = build_es_partial_update_doc(doc, job_post, fields)
                partial_update_es_document(index="job_post_index", doc_id=job_post.id, doc_data=partial_doc)
            else:
                doc.update(job_post)
        except ElasticsearchException as e:
            logger.error(f"[ES Sync] Failed to update JobPost(id={job_post.id}): {e}", exc_info=True)

    @classmethod
    def delete(cls, job_post: JobPostModel) -> None:
        """
        - Delete a single job post from elasticsearch.
        - Main entry point to delete a job post from elasticsearch.
        :param job_post: JobPostModel
        :return: None
        """
        try:
            logger.debug(f"[ES Sync] Delete JobPost(id={job_post.id}) from elasticsearch")
            JobPostDocument().delete(job_post)
        except ElasticsearchException as e:
            logger.error(f"[ES Sync] Failed to delete JobPost (id={job_post.id}): from elasticsearch: {e}",
                         exc_info=True)

    @classmethod
    def bulk_sync(cls, job_posts: QuerySet, fields: Optional[List[str]] = None) -> None:
        """
        Bulk sync job posts to Elasticsearch.

        Args:
            job_posts (QuerySet): Django queryset of JobPostModel instances to sync.
            fields (Optional[List[str]]): If specified, sync only these fields (partial update).

        Returns:
            None
        """
        from elasticsearch.exceptions import ElasticsearchException

        # Assuming JobPostDocument is your Elasticsearch DSL Document class
        doc = JobPostDocument()

        for job_post in job_posts:
            try:
                if fields:
                    # Build partial update document for fields
                    partial_doc = build_es_partial_update_doc(doc, job_post, fields)
                    partial_update_es_document(
                        index="job_post_index",
                        doc_id=job_post.id,
                        doc_data=partial_doc,
                    )
                else:
                    # Full update of the document in ES
                    doc.update(job_post)
            except ElasticsearchException as e:
                logger.error(f"[ES Sync] Failed to sync JobPost(id={job_post.id}): {e}", exc_info=True)
                # Optionally, you could collect failures to retry or raise here

    @classmethod
    def sync_related_instance(cls, instance) -> None:
        job_post = getattr(instance, 'job_post', None)
        if not job_post:
            return
        fields = cls.get_sync_fields_for_related(instance)
        cls.sync(job_post, fields=fields)

    @staticmethod
    def sync_delete(job_post_id: int):
        """
        Removes a job post document from Elasticsearch index.
        :param job_post_id: ID of the job post to remove
        """
        try:
            JobPostDocument().get(id=job_post_id).delete()
            logger.info(f"[ES DELETE] JobPost id={job_post_id} removed from index.")
        except NotFoundError:
            logger.warning(f"[ES DELETE] JobPost id={job_post_id} not found in index.")
        except Exception as e:
            logger.error(f"[ES DELETE] Failed to delete JobPost id={job_post_id}: {e}")
            raise


    @staticmethod
    def get_job_post(job_post_id: int):
        job = (
            JobPostDocument.search()
            .query("term", id=job_post_id)
            .execute()
        )
        return job[0] if job else None