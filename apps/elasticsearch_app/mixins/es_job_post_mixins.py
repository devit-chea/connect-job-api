from copy import deepcopy

from apps.base.models.company_model import Company
from apps.base.utils.file_management_util import FileURLService, _to_uuid
from apps.elasticsearch_app.constants.es_constants import ORDERING_FIELDS
from apps.job_management_app.models.job_category_model import JobCategoryModel


class JobPostImageContextMixin:
    """
    Batch-fetches company image URLs and category icon URLs for the whole page.
    Stores results in serializer context as _company_pic_map, _file_url_map, _category_icon_map.
    """

    def _build_image_context(self, page):
        company_ids = []
        category_names = []

        for hit in page or []:
            company = getattr(hit, "company", None)
            cid = (
                company.get("id")
                if isinstance(company, dict)
                else getattr(company, "id", None)
            )
            if cid:
                company_ids.append(cid)

            category = getattr(hit, "category", None)
            if category:
                category_names.append(category)

        company_pic_map = {}
        if company_ids:
            companies = Company.objects.filter(id__in=company_ids).only(
                "id", "profile_picture_id"
            )
            company_pic_map = {str(c.id): c.profile_picture_id for c in companies}

        file_ids = [pid for pid in company_pic_map.values() if pid]
        file_url_map = FileURLService.map_by_file_ids(file_ids) if file_ids else {}
        category_icon_map = self._build_category_icon_map(category_names)

        return {
            "_company_pic_map": company_pic_map,
            "_file_url_map": file_url_map,
            "_category_icon_map": category_icon_map,
        }

    @staticmethod
    def _build_category_icon_map(category_names):
        unique_names = {name for name in category_names if name}
        if not unique_names:
            return {}
        categories = JobCategoryModel.objects.filter(name__in=unique_names).only(
            "id", "name", "profile_picture_id"
        )
        cat_file_ids = [
            cat.profile_picture_id for cat in categories if cat.profile_picture_id
        ]
        cat_url_map = (
            FileURLService.map_by_file_ids(cat_file_ids) if cat_file_ids else {}
        )
        return {
            cat.name: (cat_url_map.get(_to_uuid(cat.profile_picture_id)) or {}).get(
                "file_path"
            )
            for cat in categories
        }


class ESSortMixin:
    """Provides methods for standardizing and applying sort fields for Elasticsearch."""

    # Map user-friendly field names to Elasticsearch document fields
    _ALLOWED_SORT_FIELDS = deepcopy(ORDERING_FIELDS)

    def _get_es_sort_list(self, ordering_fields):
        """Converts comma-separated field string/list into an Elasticsearch sort list."""
        if isinstance(ordering_fields, str):
            ordering_fields = ordering_fields.split(",")

        sort_list = []
        for field in ordering_fields:
            direction = "asc"
            raw_field = field.strip()

            if raw_field.startswith("-"):
                direction = "desc"
                raw_field = raw_field[1:]

            es_field = self._ALLOWED_SORT_FIELDS.get(raw_field)
            if es_field:
                sort_list.append({es_field: {"order": direction}})

        return sort_list
