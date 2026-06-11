from elasticsearch_dsl import Q


def build_strict_title_gate(job_post):
    title = job_post.title

    return Q(
        "bool",
        should=[
            # 1️ Exact current position
            Q("term", **{"current_position.raw": title}),
            # 2️ Phrase match (Senior Backend Developer)
            Q("match_phrase", current_position={"query": title, "slop": 2}),
            # 3️ Token match on current position
            Q(
                "match",
                current_position={
                    "query": title,
                    "operator": "and",
                    "minimum_should_match": "60%",
                },
            ),
            # 4️ Past job titles (career history)
            Q(
                "nested",
                path="work_experiences",
                query=Q(
                    "match",
                    **{
                        "work_experiences.job_title": {
                            "query": title,
                            "operator": "and",
                            "minimum_should_match": "60%",
                        }
                    }
                ),
            ),
            # 5️ Job preference
            Q("terms", **{"job_preference.position_titles": [title]}),
        ],
        minimum_should_match=1,
    )


def build_es_recommend_applicant_query(job_post, min_score_threshold):

    title_gate = build_strict_title_gate(job_post)

    # --- Soft ranking ---
    text_query = Q(
        "bool",
        should=[
            Q(
                "multi_match",
                query=job_post.job_description,
                fields=["about_me^2", "about_me.ngram"],
            ),
            Q(
                "match_phrase",
                current_position={"query": job_post.title, "slop": 1, "boost": 6},
            ),
            Q("match", current_position={"query": job_post.title, "boost": 10}),
            Q(
                "nested",
                path="work_experiences",
                query=Q(
                    "multi_match",
                    query=job_post.job_description,
                    fields=[
                        "work_experiences.job_title^2",
                        "work_experiences.job_description",
                    ],
                ),
            ),
        ],
        minimum_should_match=1,
    )

    base_query = Q(
        "bool", must=[title_gate, text_query]  # Who is allowed  # Who is best
    )

    # --- Structured boosts ---
    functions = []

    if job_post.title:
        functions.append(
            {
                "filter": {
                    "terms": {"job_preference.position_titles": [job_post.title]}
                },
                "weight": 15,
            }
        )

    if job_post.remote_type:
        functions.append(
            {
                "filter": {
                    "terms": {"job_preference.work_type": [job_post.remote_type]}
                },
                "weight": 3,
            }
        )

    if job_post.time_type:
        functions.append(
            {
                "filter": {"terms": {"job_preference.employment_type": [job_post.time_type]}},
                "weight": 3,
            }
        )

    if job_post.location:
        functions.append(
            {
                "filter": {
                    "terms": {"job_preference.job_location": [job_post.location]}
                },
                "weight": 2.5,
            }
        )

    return Q(
        "function_score",
        query=base_query,
        functions=functions,
        score_mode="sum",
        boost_mode="sum",
        min_score=min_score_threshold,
    )
