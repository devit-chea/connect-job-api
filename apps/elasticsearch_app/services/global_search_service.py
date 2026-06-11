from elasticsearch_dsl import Q
from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.base.models.geo_area_model import GeoArea
from apps.elasticsearch_app.constants.es_constants import (
    COMPANY_SEARCH_FIELDS,
    PEOPLE_SEARCH_FIELDS,
)
from apps.elasticsearch_app.queries.compay_builder_query import CompanySearchFilters
from apps.elasticsearch_app.search.global_search_document import (
    CompanyDocument,
    ProfileDocument,
)


class GlobalSearchService:
    def __init__(self, search_term, user=None, industry_filter=None, location_filter=None):
        self.search_term = search_term
        self.industry_filter = industry_filter
        self.location_filter = location_filter
        self.user = user

    def search_companies(self):
        """
        Queries the 'companies' index.
        """
        q = CompanyDocument.search()
        filters = [CompanySearchFilters.get_public_status_filter()]

        if self.industry_filter:
            filters.append(Q("term", **{"industry.raw": self.industry_filter}))
        if self.location_filter:
            # Get location id
            get_city = GeoArea.objects.filter(name=self.location_filter).first()
            if get_city:
                filters.append(Q("term", city_id=get_city.id))

        if self.search_term:
            q = q.query(
                "multi_match",
                query=self.search_term,
                fields=COMPANY_SEARCH_FIELDS,
                type="best_fields",
                fuzziness="AUTO",
            )
        else:
            q = q.query("match_all")

        q = q.filter("bool", must=filters)

        return q

    def search_people_profiles(self):
        """
        Queries the 'profiles' index
        """
        if not self.search_term:
            base_query = Q("match_all")
        else:
            base_query = Q(
                "multi_match",
                query=self.search_term,
                fields=PEOPLE_SEARCH_FIELDS,
                type="best_fields",
                fuzziness="AUTO",
            )

        q = (
            ProfileDocument.search()
            .query(base_query)
            .filter(Q("term", profile_type=UserTypes.APPLICANT.value))
        )

        return q
