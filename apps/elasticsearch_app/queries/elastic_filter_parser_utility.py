from collections import defaultdict
from typing import List, Dict, Any

from elasticsearch_dsl import Q


class ESFilterParser:
    """
    # ne => mean not equal to
    # in => mean in list
    # range => mean between two values
    # wildcard => mean any value
    # gte => mean greater than or equal to
    # lte => mean less than or equal to
    # gt => mean greater than
    # lt => mean less than
    # term => mean exact match
    """

    def op_in(f, v):
        if isinstance(v, list):
            return Q("terms", **{f: v})
        if isinstance(v, (str, int, float)):
            return Q("terms", **{f: [v]})
        return Q("match_none")

    OPERATORS = {
        "ne": lambda f, v: ~Q("term", **{f: v}),
        "in": op_in,
        "range": lambda f, v: (
            Q("range", **{f: {"gte": v[0], "lte": v[1]}})
            if isinstance(v, (list, tuple)) and len(v) == 2
            else Q("match_none")
        ),
        "wildcard": lambda f, v: Q("wildcard", **{f: v}),
        "gte": lambda f, v: Q("range", **{f: {"gte": v}}),
        "lte": lambda f, v: Q("range", **{f: {"lte": v}}),
        "gt": lambda f, v: Q("range", **{f: {"gt": v}}),
        "lt": lambda f, v: Q("range", **{f: {"lt": v}}),
        "term": lambda f, v: Q("term", **{f: v}),
    }

    def __init__(
        self, filters: Dict[str, Any], allowed_fields: Dict[str, Dict[str, Any]]
    ):
        self.filters = filters
        self.allowed_fields = allowed_fields

    def parse(self) -> List[Q]:
        queries = []

        for raw_key, value in self.filters.items():
            if not isinstance(raw_key, str):
                continue

            # extract operator
            parts = raw_key.rsplit("__", 1)
            input_field = parts[0]
            op = parts[1] if len(parts) == 2 else "term"

            if input_field not in self.allowed_fields:
                continue

            conf = self.allowed_fields[input_field]
            es_field = conf["path"]

            builder = self.OPERATORS.get(op)
            if not builder:
                continue

            base_query = builder(es_field, value)

            if conf.get("nested", False):
                nested_path = conf["nested_path"]
                wrapped_query = Q("nested", path=nested_path, query=base_query)
                queries.append(wrapped_query)
            else:
                queries.append(base_query)

        return queries
