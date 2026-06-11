from apps.elasticsearch_app.services.job_similarity_service import JobSimilarityService
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from apps.job_management_app.serializers.job_post_serializer import SimilarJobPostListSerializer

@extend_schema(
    description="For applicants: recommend similar jobs based on a given job's title, description, and skills.",
    summary="Get similar job posts",
    parameters=[
        OpenApiParameter(
            name='id', 
            type=OpenApiTypes.INT, 
            location=OpenApiParameter.PATH, 
            description='The ID of the job post to find similar jobs for.',
            required=True
        ),
        OpenApiParameter(
            name='page_size', 
            type=OpenApiTypes.INT, 
            location=OpenApiParameter.QUERY, 
            description='Number of similar job posts to return (default: 10).',
            default=10
        ),
    ],
    responses={
        200: SimilarJobPostListSerializer(many=True),
        401: {'description': 'Authentication credentials were not provided.'},
        404: {'description': 'Not Found: The job with the given ID does not exist.'},
    }
)
class SimilarJobView(APIView):
    """
    For applicants: recommend similar jobs based on title, description, skills
    """
    permission_classes = []
    
    similarity_service = JobSimilarityService() 

    def get(self, request, id):
        page_size = int(request.query_params.get("page_size", 10))

        try:
            # The service handles finding the job and the similarity logic
            jobs = self.similarity_service.get_similar_jobs(job_id=id, page_size=page_size)
        except NotFound as e:
            return Response({"detail": str(e)}, status=404)

        serializer = SimilarJobPostListSerializer(jobs, many=True)
        return Response(serializer.data)