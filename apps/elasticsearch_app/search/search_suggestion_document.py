from django_elasticsearch_dsl import Document, fields, Index
from django_elasticsearch_dsl.registries import registry

from apps.base.models.company_model import Company
from apps.job_management_app.models.job_post_model import JobPostModel


company_index = Index("companies")
company_index.settings(number_of_shards=1, number_of_replicas=0)

# Define the index
job_index = Index("jobs")
job_index.settings(number_of_shards=1, number_of_replicas=0)


@registry.register_document
class JobDocument(Document):
    # Autocomplete fields
    title = fields.TextField(
        fields={
            "raw": fields.KeywordField(),
            "suggest": fields.CompletionField(),
            "as_you_type": fields.SearchAsYouTypeField(),
        }
    )
    skills = fields.TextField(fields={"as_you_type": fields.SearchAsYouTypeField()})

    # Add other fields if you want them searchable
    description = fields.TextField()

    class Index:
        # Name of the Elasticsearch index
        name = "jobs"
        settings = {"number_of_shards": 1, "number_of_replicas": 0}

    class Django:
        model = JobPostModel
        fields = ["id", "create_date", "write_date", "expire_date"]


@registry.register_document
class CompanyDocument(Document):
    name = fields.TextField(
        fields={
            "raw": fields.KeywordField(),
            "suggest": fields.CompletionField(),
            "as_you_type": fields.SearchAsYouTypeField()
        }
    )
    logo_url = fields.TextField()

    class Index:
        name = "companies"
        
    class Django:
        model = Company
        fields = ["id"]
