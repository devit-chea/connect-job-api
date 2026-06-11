from django.shortcuts import get_object_or_404
from apps.elasticsearch_app.models.job_post_document import JobPostDocument
from apps.job_management_app.models.job_post_model import JobPostModel
from rest_framework.exceptions import NotFound
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes


class JobSimilarityService:
    """
    A service class for fetching jobs similar to a given job post.
    Uses Elasticsearch's More Like This query via JobPostDocument.
    """

    def __init__(self, document_class=JobPostDocument, model_class=JobPostModel):
        self.document_class = document_class
        self.model_class = model_class

    def get_similar_job_ids(self, job_id, page_size=10):
        """
        Executes the 'More Like This' query and returns a list of similar job IDs.
        """
        query = {
            "query": {
                "more_like_this": {
                    "fields": ["title", "location", "category"],
                    "like": [{"_id": str(job_id)}],
                    "min_term_freq": 1,
                    "max_query_terms": 25,
                    "minimum_should_match": "75%",
                }
            },
            "post_filter": {"bool": {"must_not": {"term": {"_id": str(job_id)}}}},
            "size": page_size,
        }

        search = self.document_class.search().from_dict(query)
        search = search.filter("term", status=JobPostStatusTypes.ACTIVE.value.lower())
        results = search.execute()

        return [hit.meta.id for hit in results]

    def get_similar_jobs(self, job_id, page_size=10):
        """
        Fetches the actual JobPost model instances for similar jobs.
        """
        get_object_or_404(
            self.model_class, id=job_id, status=JobPostStatusTypes.ACTIVE.value
        )
        job_ids = self.get_similar_job_ids(job_id, page_size)
        jobs = self.model_class.objects.filter(id__in=job_ids)

        jobs_dict = {str(job.id): job for job in jobs}
        ordered_jobs = [jobs_dict[id_] for id_ in job_ids if id_ in jobs_dict]

        return ordered_jobs
