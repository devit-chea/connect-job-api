import uuid

from django.utils import timezone
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry

from apps.activity_tracking_app.models.job_post_user_activity_count_model import JobPostUserActivityCountModel
from apps.auth_oauth.models.profile_model import Profile
from apps.base.models.company_model import Company
from apps.base.utils.file_management_util import FileURLService
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.models.job_post_additional_field_model import JobPostAdditionalFieldModel
from apps.job_management_app.models.job_post_model import JobPostModel


@registry.register_document
class CompanyDocument(Document):
    name = fields.TextField(
        analyzer="edge_ngram_analyzer",
        search_analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "suggest": fields.CompletionField(),
        },
    )
    industry = fields.TextField(fields={"raw": fields.KeywordField()})
    description = fields.TextField()
    address = fields.TextField()
    jobs_open_count = fields.IntegerField()
    company_size = fields.TextField()
    profile_picture_id = fields.TextField()
    cover_picture_id = fields.TextField()
    city_id = fields.IntegerField()
    is_active = fields.BooleanField()
    status = fields.TextField()

    class Index:
        name = "search_companies"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "tokenizer": {
                    "edge_ngram_analyzer": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 20,
                        "token_chars": ["letter", "digit"],
                    }
                },
                "analyzer": {
                    "edge_ngram_analyzer": {
                        "type": "custom",
                        "tokenizer": "edge_ngram_analyzer",
                        "filter": ["lowercase"],
                    }
                },
            },
        }

    class Django:
        model = Company
        auto_refresh = True
        fields = [
            "id",
            "phone_number",
            "website",
            "email",
            "about_me",
            "found_date",
            "postal_code",
            "is_agree_policy"
        ]

    def prepare_jobs_open_count(self, instance):
        """Precompute open job count during indexing"""
        return JobPostModel.objects.filter(
            company_id=instance.id,
            status=JobPostStatusTypes.ACTIVE.value,
            expire_date__gte=timezone.localdate(),
        ).count()


@registry.register_document
class JobDocument(Document):
    title = fields.TextField(
        analyzer="edge_ngram_analyzer",
        search_analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "suggest": fields.CompletionField(),
        },
    )
    location = fields.TextField(
        analyzer="edge_ngram_analyzer",
        search_analyzer="standard",
        fields={
            "raw": fields.KeywordField(),
            "suggest": fields.CompletionField(),
        },
    )
    job_description = fields.TextField(
        analyzer='edge_ngram_analyzer',
        search_analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'suggest': fields.CompletionField(),
        }
    )
    job_requirement = fields.TextField()
    company_name = fields.TextField(attr="company.name")
    salary_min = fields.FloatField()
    salary_max = fields.FloatField()
    profile_image_url = fields.TextField()
    company_industry = fields.TextField(
        attr="company.industry", fields={"keyword": fields.KeywordField()}
    )
    category = fields.TextField(fields={"raw": fields.KeywordField()})

    class Index:
        name = "search_jobs_post"
        settings = {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "tokenizer": {
                    "edge_ngram_analyzer": {
                        "type": "edge_ngram",
                        "min_gram": 2,
                        "max_gram": 20,
                        "token_chars": ["letter", "digit"],
                    }
                },
                "analyzer": {
                    "edge_ngram_analyzer": {
                        "type": "custom",
                        "tokenizer": "edge_ngram_analyzer",
                        "filter": ["lowercase"],
                    }
                },
            },
        }

    class Django:
        model = JobPostModel
        fields = [
            "id",
            "salary_type",
            "salary_currency",
            "time_type",
            "post_date",
            "expire_date",
            "remote_type",
        ]
        related_models = [Company]
        
    @staticmethod
    def get_instances_from_related(related_instance):
        if isinstance(related_instance, JobPostAdditionalFieldModel):
            return related_instance.job_post
        if isinstance(related_instance, Company):
            return JobPostModel.objects.filter(company_id=related_instance.pk)
        if isinstance(related_instance, JobPostUserActivityCountModel):
            return related_instance.job_post

    def get_indexing_queryset(self):
        return (
            self.get_queryset()
            .select_related('user_activity_count')  # use select_related for 1:1 relationship
            .prefetch_related('additional_field')
            .iterator(chunk_size=200)
        )

    # Optional override if used elsewhere
    def get_queryset(self):
        return super().get_queryset().filter(status=JobPostStatusTypes.ACTIVE, is_deleted=False)
    
    def prepare_profile_image_url(self, instance):
        """Fetch logo via company → storage"""
        try:
            company = Company.objects.get(id=instance.company_id)
            presentation = FileURLService.present_profile_images(company)
            return (presentation.get("profile_image") or {}).get("file_path")
        except (Company.DoesNotExist, ValueError):
            return None

    def prepare_salary_min(self, instance):
        if instance.salary_range:
            return (
                float(instance.salary_range.lower)
                if instance.salary_range.lower is not None
                else None
            )

    def prepare_salary_max(self, instance):
        if instance.salary_range:
            return (
                float(instance.salary_range.upper)
                if instance.salary_range.upper is not None
                else None
            )


@registry.register_document
class ProfileDocument(Document):
    full_name = fields.TextField(fields={"keyword": fields.KeywordField()})
    current_position = fields.TextField()
    company_name = fields.TextField(attr="company.name")
    profile_picture_id = fields.TextField()

    class Index:
        name = "search_profiles"
        settings = {"number_of_shards": 1, "number_of_replicas": 0}

    class Django:
        model = Profile
        fields = [
            "id",
            "location_name",
            "first_name",
            "last_name",
            "profile_type",
        ]
        related_models = [Company]

    @staticmethod
    def get_instances_from_related(related_instance):
        if isinstance(related_instance, Company):
            return JobPostModel.objects.filter(company_id=related_instance.pk)