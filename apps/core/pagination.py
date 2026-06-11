from rest_framework.pagination import PageNumberPagination, _positive_int
from rest_framework.response import Response


DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10
CONSTANT_TRUE = ["true", "True"]
CONSTANT_FALSE = ["False", "false"]


class CustomPagination(PageNumberPagination):
    page = DEFAULT_PAGE
    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"

    def get_paginated_response(self, data):
        request = getattr(self, "request", None)
        
        paging = "true"
        if request:
            paging = request.GET.get("paging", "true")
            
        if paging in CONSTANT_TRUE:
            return Response(
                {
                    "count": self.page.paginator.count,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                    # can not set default = self.page
                    "page": int(self.request.GET.get("page", DEFAULT_PAGE)),
                    "page_size": int(self.request.GET.get("page_size", self.page_size)),
                    "results": data,
                }
            )
        else:
            return Response(data)

    def get_page_size(self, request):
        paging = request.query_params.get("paging", "true")
        page_size = super().get_page_size(request)
        if paging in CONSTANT_FALSE:
            page_size = None

        return page_size