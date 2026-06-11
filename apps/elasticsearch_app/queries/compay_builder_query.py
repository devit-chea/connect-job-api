from elasticsearch_dsl import Q
from apps.base.constants.base_constants import Status


class CompanySearchFilters:
    """Utility class for generating common Elasticsearch filters for Company documents."""

    @staticmethod
    def get_public_status_filter():
        """
        Returns an Elasticsearch Q object filtering for approved and active companies.
        
        Equivalent to: Q('term', status=Status.APPROVED) & Q('term', is_active=True)
        """
        
        return Q(
            'term', status=Status.APPROVED.lower()
        ) & Q(
            'term', is_active=True
        )
