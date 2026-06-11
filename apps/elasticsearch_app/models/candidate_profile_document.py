from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.auth_oauth.models.auth_models import User
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.user_company_profile import UserCompanyProfile


@registry.register_document
class CandidateProfileDocument(Document):
    user_id = fields.IntegerField(attr="user.id")
    profile_id = fields.IntegerField(attr="profile.id")
    company_id = fields.IntegerField(attr="company.id")

    job_preference = fields.ObjectField(
        properties={
            "work_type": fields.TextField(multi=True),
            "job_location": fields.TextField(multi=True),
            "employment_type": fields.TextField(multi=True),
            "position_titles": fields.TextField(multi=True),
            "excepted_salary": fields.ObjectField(
                properties={
                    "min": fields.FloatField(),
                    "max": fields.FloatField(),
                }
            ),
        }
    )
    about_me = fields.TextField()
    current_position = fields.TextField()

    class Index:
        name = "candidate_profile_index"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        }

    class Django:
        model = UserCompanyProfile
        fields = ["id", "type"]
        related_models = [User, Profile]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(
                # user__is_active=True,
                type=UserTypes.APPLICANT.value
            )
        )

    @staticmethod
    def prepare_job_preference(instance):
        """
        Flatten job_preference JSON (dict/list) into a search-friendly string.
        """
        if instance.profile and isinstance(instance.profile.job_preference, dict):
            return instance.profile.job_preference
        return {}

    def prepare_about_me(self, instance):
        return instance.profile.about_me if instance.profile else ""

    @staticmethod
    def get_instances_from_related(related_instance):
        """
        Given a related instance (User or Profile), return UserCompanyProfile queryset
        to be re-indexed.
        """
        from apps.auth_oauth.models.user_company_profile import UserCompanyProfile
        from apps.auth_oauth.models.auth_models import User
        from apps.auth_oauth.models.profile_model import Profile

        if isinstance(related_instance, User):
            # Related name from UserCompanyProfile model: user_company_profile_user
            return related_instance.user_company_profile_user.all()

        elif isinstance(related_instance, Profile):
            return UserCompanyProfile.objects.filter(profile=related_instance)

        return UserCompanyProfile.objects.none()

    def prepare_current_position(self, instance):
        return instance.profile.current_position if instance.profile else ""
