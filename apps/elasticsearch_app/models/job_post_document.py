from django.utils import timezone

from django_elasticsearch_dsl import fields, Document
from django_elasticsearch_dsl.registries import registry

from apps.activity_tracking_app.models.job_post_user_activity_count_model import JobPostUserActivityCountModel
from apps.base.models.company_model import Company
from apps.base.utils.file_management_util import FileURLService
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from apps.job_management_app.models.job_post_additional_field_model import JobPostAdditionalFieldModel
from apps.job_management_app.models.job_post_model import JobPostModel


@registry.register_document
class JobPostDocument(Document):
    # Define full-text searchable fields with auto complete support
    title = fields.TextField(
        analyzer='edge_ngram_analyzer',
        search_analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'suggest': fields.CompletionField(),
        }
    )
    location = fields.TextField(
        analyzer='edge_ngram_analyzer',
        search_analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'suggest': fields.CompletionField(),
        }
    )
    job_description = fields.TextField(
        analyzer='edge_ngram_analyzer',
        search_analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'suggest': fields.CompletionField(),
        }
    )
    salary_min = fields.FloatField(attr='_prepare_salary_min')
    salary_max = fields.FloatField(attr='_prepare_salary_max')
    natures = fields.NestedField(properties={
        'code': fields.TextField(),
        'name': fields.TextField(),
        'description': fields.TextField(),
    })
    job_level = fields.TextField(
        analyzer='edge_ngram_analyzer',
        search_analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'suggest': fields.CompletionField(),
        }
    )
    time_type = fields.TextField(
        analyzer='edge_ngram_analyzer',
        search_analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'suggest': fields.CompletionField(),
        }
    )
    remote_type = fields.TextField(
        analyzer='edge_ngram_analyzer',
        search_analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'suggest': fields.CompletionField(),
        }
    )
    category = fields.TextField(
        analyzer='edge_ngram_analyzer',
        search_analyzer='standard',
        fields={
            'raw': fields.KeywordField(),
            'suggest': fields.CompletionField(),
        }
    )
    company = fields.NestedField(properties={
        "id": fields.IntegerField(),
        'name': fields.TextField(),
        'profile_picture_id': fields.TextField(),
        'email': fields.TextField(),
    })

    view_count = fields.IntegerField()
    save_count = fields.IntegerField()
    apply_count = fields.IntegerField()
    priority_order = fields.IntegerField()

    class Index:
        name = 'job_post_index'
        settings = {
            'number_of_shards': 1,
            'number_of_replicas': 1,
            'analysis': {
                'tokenizer': {
                    'edge_ngram_analyzer': {
                        'type': 'edge_ngram',
                        'min_gram': 2,
                        'max_gram': 20,
                        'token_chars': ['letter', 'digit']
                    }
                },
                'analyzer': {
                    'edge_ngram_analyzer': {
                        'type': 'custom',
                        'tokenizer': 'edge_ngram_analyzer',
                        'filter': ['lowercase']
                    }
                }
            },
        }

    class Django:
        model = JobPostModel
        fields = [
            'id',
            'job_code',
            'post_date',
            'expire_date',
            'privacy_type',
            'contract_type',
            'is_active',
            'status',
            'create_date',
            'write_date',
            'priority',
            'salary_type',
            'salary_currency',
            'hire_no',
            'year_of_experience',
        ]

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
        return (
            super()
            .get_queryset()
            .filter(
                status=JobPostStatusTypes.ACTIVE,
                is_deleted=False,
                expire_date__gte=timezone.now(),
            )
        )

    @staticmethod
    def prepare_salary_min(instance):
        if instance.salary_range:
            return float(instance.salary_range.lower)
        return None

    @staticmethod
    def prepare_salary_max(instance):
        if instance.salary_range:
            return float(instance.salary_range.upper)
        return None

    @staticmethod
    def _prepare_additional_field_by_name(instance, target_name):
        return [
            {
                'code': a.code,
                'name': a.name,
                'description': a.description
            }
            for a in instance.additional_field.all()
            if a.field_name == target_name
        ]

    @staticmethod
    def prepare_natures(instance):
        return JobPostDocument._prepare_additional_field_by_name(instance, 'natures')

    @staticmethod
    def prepare_company(instance):
        company = instance.company
        if not company:
            return None
        return {
            "id": company.id,
            "name": company.name,
            "profile_picture_id": company.profile_picture_id,
            "email": company.email,
            "profile_image_url": JobPostDocument.get_profile_image_url(instance),
        }

    @staticmethod
    def prepare_view_count(instance):
        uac = getattr(instance, 'user_activity_count', None)
        return uac.view_count if uac else 0

    @staticmethod
    def prepare_save_count(instance):
        uac = getattr(instance, 'user_activity_count', None)
        return uac.save_count if uac else 0

    @staticmethod
    def prepare_apply_count(instance):
        uac = getattr(instance, 'user_activity_count', None)
        return uac.apply_count if uac else 0

    @staticmethod
    def prepare_priority_order(instance):
        priority_map = {'URGENT': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
        return priority_map.get(instance.priority, 0)

    @staticmethod
    def get_profile_image_url(instance):
        try:
            company = Company.objects.get(id=instance.company_id)
            presentation = FileURLService.present_profile_images(company)
            return (presentation.get("profile_image") or {}).get("file_path")
        except (Company.DoesNotExist, ValueError):
            return None
