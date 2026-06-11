from rest_framework import serializers


class ApplicantScoreSerializer(serializers.Serializer):
    """Serializer for a single recommended applicant and their score."""

    # Updated field names to match the service output
    applicant_profile_id = serializers.IntegerField(
        help_text="ID of the recommended applicant profile."
    )
    full_name = serializers.CharField(
        max_length=255, help_text="Full name of the applicant."
    )
    current_position = serializers.CharField(
        max_length=255, allow_null=True, help_text="Applicant's current job title."
    )
    location_name = serializers.CharField(
        max_length=255, allow_null=True, help_text="Applicant's location."
    )
    phone_number = serializers.CharField(
        max_length=50, allow_null=True, help_text="Applicant's phone number."
    )
    percentage_score = serializers.IntegerField(
        help_text="Matching score percentage (0-100)."
    )
    score_category = serializers.CharField(
        max_length=50, help_text="Category of the match (e.g., 'Strong', 'Good')."
    )
    profile_picture_url = serializers.CharField(
        max_length=512, allow_null=True, help_text="URL path to the profile picture."
    )


class RecommendedApplicantsResponseSerializer(serializers.Serializer):
    """Serializer for the final API response structure."""

    job_id = serializers.IntegerField(help_text="ID of the Job Post.")
    job_title = serializers.CharField(
        max_length=255, help_text="Title of the Job Post."
    )
    total_matching_applicants = serializers.IntegerField(
        help_text="Total count of applicants matching the criteria."
    )
    applicants = ApplicantScoreSerializer(
        many=True, help_text="List of recommended applicants with scores."
    )
