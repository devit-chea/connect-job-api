from django_elasticsearch_dsl_drf.serializers import DocumentSerializer
from rest_framework import serializers

from apps.base.decorators.datetime_format_decorator import datetime_format_decorator
from apps.elasticsearch_app.models.job_post_document import JobPostDocument
from apps.base.utils.file_management_util import FileURLService, _to_uuid
from apps.base.models.company_model import Company
from apps.job_management_app.models.job_category_model import JobCategoryModel

class JobPostListSerializer(serializers.ListSerializer):
    def to_representation(self, data):
        """
        Pre-build the category icon map once before iterating,
        so all children share the same cached lookup.
        """
        # Collect all category names upfront
        instances = list(data)
        category_names = []
        for instance in instances:
            if isinstance(instance, dict):
                category_names.append(instance.get("category") or "")
            else:
                rep = super().child.to_representation(instance)
                category_names.append((rep or {}).get("category") or "")

        # Pre-warm the cache into context
        self.child._get_category_icon_map(category_names)

        # Now serialize normally — each child hits the cache
        return super().to_representation(instances)


@datetime_format_decorator(
    fields=["create_date", "write_date", "post_date"], use_timezone=True
)
class JobPostDocumentSerializer(DocumentSerializer):
    is_saved = serializers.BooleanField(read_only=True, default=False)
    is_applied = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        document = JobPostDocument
        fields = "__all__"

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data is None:
            return None

        company = data.get("company") or {}
        company_pic_map = self.context.get("_company_pic_map", {})
        file_url_map = self.context.get("_file_url_map", {})
        pid = _to_uuid(company_pic_map.get(str(company.get("id") or "")))
        company["profile_image_url"] = (file_url_map.get(pid) or {}).get("file_path") if pid else None
        data["company"] = company

        category_icon_map = self.context.get("_category_icon_map", {})
        data["category_icon"] = category_icon_map.get(data.get("category") or "")

        return data
