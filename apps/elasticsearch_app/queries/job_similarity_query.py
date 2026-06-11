from elasticsearch_dsl import Q, Search


def build_job_similarity_query(profile_doc, page=1, page_size=10):
    about_me_text = profile_doc.about_me or ""

    preference = (
        profile_doc.job_preference.to_dict()
        if hasattr(profile_doc.job_preference, "to_dict")
        else profile_doc.job_preference or {}
    )
    position_titles = preference.get("position_titles", [])
    combined_text = f"{about_me_text} {' '.join(position_titles)}".strip()

    filters = []

    if work_types := preference.get("work_type"):
        filters.append(Q("terms", remote_type=work_types))

    if locations := preference.get("job_location"):
        filters.append(Q("terms", location=locations))

    if employment_types := preference.get("employment_type"):
        filters.append(Q("terms", time_type=employment_types))

    if salary := preference.get("excepted_salary", {}):
        if salary.get("min") is not None:
            filters.append(
                Q("range", **{"salary_structure.max_salary": {"gte": salary["min"]}})
            )
        if salary.get("max") is not None:
            filters.append(
                Q("range", **{"salary_structure.min_salary": {"lte": salary["max"]}})
            )

    # Start base search
    s = Search(index="job_post_index")
    s = s[(page - 1) * page_size : page * page_size]  # pagination
    s = s.sort("_score", "-create_date")

    must_clauses = []
    if combined_text:
        must_clauses.append(
            Q(
                "more_like_this",
                fields=["title", "job_description", "salary_structure"],
                like=combined_text,
                min_term_freq=1,
                min_doc_freq=0,
                max_query_terms=25,
            )
        )

    # Final bool query
    query = Q("bool", must=must_clauses, filter=filters)
    s = s.query(query)

    return s
