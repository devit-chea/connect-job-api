from django.db.models.aggregates import Count
from django.db.models.expressions import Exists, OuterRef

from apps.auth_oauth.models.education_model import Education
from apps.auth_oauth.models.profile_language_model import ProfileLanguage
from apps.auth_oauth.models.profile_model import ProfileDocumentModel
from apps.auth_oauth.models.work_experience_model import WorkExperience


def profile_completion_annotations(qs):
    return (
        qs.select_related("location")
        .annotate(
            educations_exists=Exists(
                Education.objects.filter(user_profile_id=OuterRef("pk"))
            ),
            work_experiences_exists=Exists(
                WorkExperience.objects.filter(user_profile_id=OuterRef("pk"))
            ),
            languages_exists=Exists(
                ProfileLanguage.objects.filter(user_profile_id=OuterRef("pk"))
            ),
            cv_exists=Exists(
                ProfileDocumentModel.objects.filter(
                    profile_id=OuterRef("pk"),
                    document_type=ProfileDocumentModel.DocumentType.CV,
                    is_deleted=False,
                )
            ),
            skills_count=Count("skill_user_profile", distinct=True),
        )
    )
