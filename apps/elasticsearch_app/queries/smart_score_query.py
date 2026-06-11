from elasticsearch_dsl import Q, Search


def build_smart_score_query(profile_doc, page=1, page_size=10):
    """
    Builds an Elasticsearch query that ranks jobs based on profile relevance.
    Uses soft relevance scoring (not strict filtering).
    """

    about_me = profile_doc.about_me or ""
    job_preference = (
        profile_doc.job_preference.to_dict()
        if hasattr(profile_doc.job_preference, "to_dict")
        else profile_doc.job_preference or {}
    )

    should_clauses = []

    # 1️ Ranking boost: EXACT job title
    if titles := job_preference.get("position_titles"):
        should_clauses.append(
            Q(
                "terms",
                **{
                    "title.keyword": titles,
                    "boost": 10,
                },
            )
        )

    # 2️ Ranking boost: location
    if locations := job_preference.get("job_location"):
        should_clauses.append(
            Q(
                "terms",
                **{
                    "location.keyword": locations,
                    "boost": 3,
                },
            )
        )

    # 3️ Ranking boost: remote / onsite
    if work_types := job_preference.get("work_type"):
        should_clauses.append(
            Q(
                "terms",
                **{
                    "remote_type.keyword": work_types,
                    "boost": 3,
                },
            )
        )

    # 4️ Ranking boost: employment type
    if employment_types := job_preference.get("employment_type"):
        should_clauses.append(
            Q(
                "terms",
                **{
                    "time_type.keyword": employment_types,
                    "boost": 3,
                },
            )
        )

    # 5️ Text relevance (ONLY place we use match)
    if about_me:
        should_clauses.append(
            Q(
                "match",
                job_description={
                    "query": about_me,
                    "fuzziness": "AUTO",
                    "boost": 1.5,
                },
            )
        )

    # 6️ Always include everything
    should_clauses.append(Q("match_all"))

    s = Search(index="job_post_index")
    s = s[(page - 1) * page_size : page * page_size]

    s = s.query(
        Q(
            "bool",
            should=should_clauses,
            minimum_should_match=0,
        )
    )

    # Primary: relevance, Secondary: recency
    s = s.sort("_score", {"create_date": {"order": "desc"}})

    return s


def build_smart_score_query_for_you(profile_doc, page=1, page_size=10):
    """
    Ranks jobs based on profile relevance using dynamic phrase matching
    to ensure title concepts stay together.
    """
    about_me = profile_doc.about_me or ""
    job_preference = (
        profile_doc.job_preference.to_dict()
        if hasattr(profile_doc.job_preference, "to_dict")
        else profile_doc.job_preference or {}
    )

    must_clauses = []
    should_clauses = []

    # 1️ TITLE — REQUIRED
    if titles := job_preference.get("position_titles"):
        title_should = []

        for title in titles:
            title_should.append(
                Q(
                    "bool",
                    should=[
                        Q("term", **{"title.keyword": {"value": title, "boost": 20}}),
                        Q(
                            "match_phrase",
                            title={"query": title, "slop": 2, "boost": 12},
                        ),
                        Q(
                            "match",
                            title={"query": title, "operator": "and", "boost": 6},
                        ),
                        Q("match", title={"query": title, "boost": 2}),
                    ],
                    minimum_should_match=1,
                )
            )

        must_clauses.append(Q("bool", should=title_should, minimum_should_match=1))

    # 2️ LOCATION — BOOST ONLY
    if locations := job_preference.get("job_location"):
        should_clauses.append(
            Q(
                "bool",
                should=[
                    Q("terms", **{"location.keyword": locations, "boost": 4}),
                    *[
                        Q("match", location={"query": loc, "boost": 2})
                        for loc in locations
                    ],
                ],
                minimum_should_match=1,
            )
        )

    # 3️ REMOTE TYPE — BOOST ONLY
    if work_types := job_preference.get("work_type", []):
        should_clauses.append(Q("terms", remote_type=work_types, boost=2.0))

    # 4 EMPLOYMENT TYPE — BOOST ONLY
    if employment_types := job_preference.get("employment_type", []):
        should_clauses.append(Q("terms", time_type=employment_types, boost=2.0))

    # 5 Boost fuzzy about_me match
    if about_me:
        should_clauses.append(
            Q("match", job_description={"query": about_me, "fuzziness": "AUTO"})
        )

    # 6 Boost salary match (soft check)
    salary_pref = job_preference.get("excepted_salary", {})
    if isinstance(salary_pref, dict):
        salary_conditions = []
        if salary_pref.get("min") is not None:
            salary_conditions.append(Q("range", salary_max={"gte": salary_pref["min"]}))
        if salary_pref.get("max") is not None:
            salary_conditions.append(Q("range", salary_min={"lte": salary_pref["max"]}))
        if salary_conditions:
            must_clauses.append(Q("bool", must=salary_conditions))

    # Fallback
    if not should_clauses:
        should_clauses.append(Q("match_all"))

    s = Search(index="job_post_index")
    s = s[(page - 1) * page_size : page * page_size]

    # Using 'should' keeps it soft relevance
    s = s.query("bool", must=must_clauses, should=should_clauses)

    # Primary sort by score, secondary by date
    s = s.sort("_score", {"create_date": {"order": "desc"}})

    return s
