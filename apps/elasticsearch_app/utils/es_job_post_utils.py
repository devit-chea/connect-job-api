import difflib
import re
from elasticsearch_dsl import Q


def create_search_query_clause(query_string, fields=None, fuzziness="AUTO"):
    """
    Constructs a combined multi_match bool query for full-text and exact searching.
    """
    if not query_string:
        return None

    # Default full-text fields
    full_text_fields = fields or ["title^3"]

    # Raw fields for exact keyword matching (assumes .raw sub-field for exactness)
    exact_fields = [f.split("^")[0] + ".raw" for f in full_text_fields]

    should_queries = [
        Q(
            "multi_match",
            query=query_string,
            fields=full_text_fields,
            fuzziness=fuzziness,
        ),
        Q(
            "multi_match",
            query=query_string,
            fields=exact_fields,
            operator="and",  # All terms must match for exact search
        ),
    ]

    return Q("bool", should=should_queries, minimum_should_match=1)


def parse_experience_range(range_string: str) -> float:
    """
    Converts a job experience range string into a numeric midpoint.
    Examples:
        '1-2 Year' -> 1.5
        '2-3 Years' -> 2.5
        '3-5 Year' -> 4.0
        '5+ Years' -> 5.0 (or configurable)
    """
    if not range_string:
        return 0.0

    # Pattern for "x-y", e.g. 1-2
    match = re.match(r"(\d+)\s*-\s*(\d+)", range_string)
    if match:
        low, high = match.groups()
        return (float(low) + float(high)) / 2.0

    # Pattern for "5+" case
    match_plus = re.match(r"(\d+)\+", range_string)
    if match_plus:
        return float(match_plus.group(1))  # lower bound

    # Fallback: extract first number
    match_num = re.search(r"\d+", range_string)
    if match_num:
        return float(match_num.group(0))

    return 0.0


def normalize_text(text):
    if not text:
        return ""
    # lowercase
    text = text.lower()
    # remove punctuation and underscores/hyphens
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fuzzy_list_match(candidate_list, job_value, threshold=0.6) -> int:
    """
    Returns 1 if job_value is similar to ANY item in candidate_list.
    Returns 0 otherwise.
    """
    if not candidate_list or not job_value:
        return 0

    job_value_norm = normalize_text(job_value)

    for item in candidate_list:
        item_norm = normalize_text(item)

        ratio = difflib.SequenceMatcher(None, item_norm, job_value_norm).ratio()

        if ratio >= threshold:
            return 1  # match found

    return 0


def default_feed_query():
    return Q(
        "function_score",
        query=Q("match_all"),
        functions=[
            {
                "gauss": {
                    "create_date": {
                        "origin": "now",
                        "scale": "7d",
                        "decay": 0.5,
                    }
                },
                "weight": 5,
            }
        ],
        score_mode="sum",
        boost_mode="sum",
    )


def job_search_query_clause(query_string, fields=None, fuzziness="AUTO"):
    if not query_string:
        return default_feed_query()

    should_queries = [
        Q(
            "match_phrase",
            title={"query": query_string, "slop": 2, "boost": 8},
        ),
        Q(
            "multi_match",
            query=query_string,
            type="cross_fields",
            operator="and",
            fields=fields,
            boost=5,
        ),
        Q(
            "multi_match",
            query=query_string,
            fields=["title^2"],
            fuzziness=fuzziness,
            prefix_length=1,
            boost=2,
        ),
        Q(
            "term",
            **{"title.raw": {"value": query_string.lower(), "boost": 10}},
        ),
    ]

    return Q(
        "bool",
        should=should_queries,
        minimum_should_match=1,
    )
