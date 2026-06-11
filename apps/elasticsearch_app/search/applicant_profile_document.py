from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from apps.auth_oauth.models.education_model import Education
from apps.auth_oauth.models.profile_model import Profile
from apps.auth_oauth.models.skill_model import Skill
from apps.auth_oauth.models.work_experience_model import WorkExperience


@registry.register_document
class ApplicantProfileDocument(Document):
    full_name = fields.TextField()
    about_me = fields.TextField(
        analyzer="english",
    )
    current_position = fields.TextField(
        analyzer="english",
        fields={
            "raw": fields.KeywordField(),
        },
    )
    location_name = fields.TextField(fields={"raw": fields.KeywordField()})
    phone_number = fields.TextField()
    skills_list = fields.ListField(fields.KeywordField())
    skills = fields.KeywordField(attr="get_skills_list", multi=True)
    work_titles = fields.TextField(attr="get_work_titles", multi=True)
    education_study_field = fields.TextField(attr="get_education_study_fields")
    job_preference = fields.ObjectField(
        properties={
            "employment_type": fields.KeywordField(multi=True),
            "work_type": fields.KeywordField(multi=True),
            "remote_type": fields.KeywordField(multi=True),
            "job_location": fields.KeywordField(multi=True),
            "position_titles": fields.KeywordField(multi=True),
        }
    )
    # --- Derived Fields for Matching & Scoring ---

    # 1. Total Job Experience (in years)
    job_experience_years = fields.FloatField(
        attr="total_experience_years"
    )  # We'll define this method on the Profile model

    # 2. Work Experience (Nested for detail and searching)
    work_experiences = fields.NestedField(
        properties={
            "job_title": fields.TextField(),
            "job_description": fields.TextField(),
            "company_name": fields.TextField(),
        },
        attr="work_experience_user_profile",  # The related_name from the WorkExperience model
    )

    # 3. Education (Nested for detail and searching)
    educations = fields.NestedField(
        properties={
            "degree": fields.KeywordField(),
            "study_field": fields.TextField(analyzer="english"),
            "description": fields.TextField(analyzer="english"),
        },
        attr="education_user_profile",  # The related_name from the Education model
    )

    # ONLY if you wanted to use the related 'Skill' model:
    def prepare_skills_list(self, instance):
        """
        Retrieves skills from the related Skill objects.
        """
        return [
            skill.name
            for skill in instance.skill_user_profile.all()
            if skill.name  # Ensure name is not empty/None
        ]

    class Index:
        name = "applicant_profiles"
        settings = {"number_of_shards": 1, "number_of_replicas": 0}

    class Django:
        model = Profile
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "profile_picture_id",
            "is_active",
        ]

        # List all related models that should trigger a re-index of the Profile document
        related_models = [WorkExperience, Education, Skill]

        # Optimization: Pre-fetch related data during indexing
        def get_queryset(self):
            return (
                self.model.objects.select_related("user", "location")
                .prefetch_related(
                    "work_experience_user_profile",
                    "education_user_profile",
                    "skill_user_profile",
                )
                .all()
            )

    @staticmethod
    def get_instances_from_related(related_instance):
        """
        Given a related instance, return the parent Profile queryset to be re-indexed.
        """
        if isinstance(related_instance, (WorkExperience, Education, Skill)):
            # Assuming all these related models have a ForeignKey to Profile named 'user_profile'
            return Profile.objects.filter(id=related_instance.user_profile_id)

        return Profile.objects.none()

    def get_work_titles(self, obj):
        return [
            we.job_title
            for we in obj.work_experience_user_profile.all()
            if we.job_title
        ]

    def get_education_study_fields(self, instance):
        return [edu.study_field for edu in instance.education.all() if edu.study_field]

    def get_skills_list(self, instance):
        return [skill.name for skill in instance.skill_user_profile.all() if skill.name]
