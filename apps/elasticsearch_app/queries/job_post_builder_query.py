import json
from copy import deepcopy

from django.http import QueryDict
from elasticsearch_dsl import Search

from apps.elasticsearch_app.constants.es_constants import FILTER_FIELDS
from apps.elasticsearch_app.mixins.es_job_post_mixins import ESSortMixin
from apps.elasticsearch_app.queries.elastic_filter_parser_utility import ESFilterParser
from apps.elasticsearch_app.utils.es_job_post_utils import create_search_query_clause
from apps.elasticsearch_app.utils.es_utils import calculate_slice_indices
from apps.job_management_app.constants.job_post_types import JobPostStatusTypes
from django.utils import timezone as dtimezone


class JobPostBuilderQuery(ESSortMixin):
    def __init__(self, index="job_post_index"):
        self.search = Search(index=index)

    def base_filter(self):
        """Apply common base filters to the search query"""
        self.search = (
            self.search.filter("term", status=JobPostStatusTypes.ACTIVE.value.lower())
            .filter("term", is_active=True)
            .filter("exists", field="title")
            .filter("exists", field="job_description")
            .filter("range", expire_date={"gte": dtimezone.now()})
        )
        return self

    def apply_search(self, query_string, fields=None, fuzziness="AUTO"):
        query_clause = create_search_query_clause(query_string, fields, fuzziness)
        if query_clause:
            self.search = self.search.query(query_clause)
        return self

    def apply_filter(self, filters_str: dict = None):
        """Apply filters to the search query"""
        if not filters_str:
            return self

        allowed_fields = deepcopy(FILTER_FIELDS)

        # Ensure the filters_str is a proper string
        if isinstance(filters_str, QueryDict):
            filters_str = filters_str.get("filters")

        try:
            filters_data = json.loads(filters_str)
        except (json.JSONDecodeError, TypeError):
            filters_data = {}

        # Normalize filters_data to a single flat dict
        combined_filters = {}
        if isinstance(filters_data, list):
            for f in filters_data:
                if isinstance(f, dict):
                    combined_filters.update(f)
        elif isinstance(filters_data, dict):
            combined_filters = filters_data

        parser = ESFilterParser(combined_filters, allowed_fields)
        queries = parser.parse()

        for q in queries:
            self.search = self.search.filter(q)

        return self

    def apply_sort(self, ordering_fields=None):
        """
        Apply sorting to the search query.
        Supports comma-separated fields like: -created_at,title
        """
        if ordering_fields:
            sort_list = self._get_es_sort_list(ordering_fields)
            if sort_list:
                self.search = self.search.sort(*sort_list)
                return self

        # Default sorting
        # Default: priority (URGENT→HIGH→MEDIUM→LOW) then newest first
        self.search = self.search.sort(
            {"priority_order": {"order": "desc"}},
            {"create_date": {"order": "desc"}},
        )
        return self

    def apply_pagination(self, page=1, page_size=10):
        """Apply pagination to the search query"""
        start, end = calculate_slice_indices(page, page_size)
        self.search = self.search[start:end]
        return self

    def build(self):
        return self.search
