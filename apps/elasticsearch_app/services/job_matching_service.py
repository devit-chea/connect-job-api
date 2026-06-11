from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.connections import connections

from apps.elasticsearch_app.utils.es_job_post_utils import fuzzy_list_match

es_client = connections.get_connection()

def normalize_similarity(value, max_value=10):
    """
    Convert BM25 or similarity score into a 0–1 scale.
    max_value=10 is standard for BM25 normalization.
    """
    value = max(value, 0)
    return min(value / max_value, 1.0)


# ---------------------------------------------------------
# 3. Weighted Final Score (0–100)
# ---------------------------------------------------------
WEIGHTS = {
    "title": 40,
    "about_me": 15,
    "experience": 15,
    "location": 10,
    "work_type": 10,
    "employment": 10,
}


def calculate_similarity_score(profile_doc, job):
    """
    Returns a score 0 to 100 based on weighted similarity between
    profile_doc profile and job.
    """
    about_me_text = profile_doc.about_me or ""

    preference = (
        profile_doc.job_preference.to_dict()
        if hasattr(profile_doc.job_preference, "to_dict")
        else profile_doc.job_preference or {}
    )
    position_titles = preference.get("position_titles", [])
    combined_text = f"{about_me_text} {' '.join(position_titles)}".strip()

    profile_text = {
        "title": position_titles,
        "about_me": combined_text or "",
        "work_type": preference.get("work_type", []),
        "location": preference.get("job_location", []),
        "employment": preference.get("employment_type", []),
    }

    job_text = {
        "title": job.title or "",
        "about_me": job.job_description or "",
        "work_type": job.remote_type or "",
        "location": job.location or "",
        "employment": job.time_type or "",
    }

    score_components = {}

    # -----------------------------
    # 1. Title similarity
    # -----------------------------
    if profile_text["title"] and job_text["title"]:
        s = Search(index="job_post_index").query(
            "more_like_this",
            fields=["title"],
            like=f"{profile_text['title']} {job_text['title']}",
            min_term_freq=1,
            min_doc_freq=0,
        )
        r = s.execute()
        score_components["title"] = r.hits.max_score or 0
    else:
        score_components["title"] = 0

    # -----------------------------
    # 2. About Me vs Job Description
    # -----------------------------
    if profile_text["about_me"] and job_text["about_me"]:
        s = Search(index="job_post_index").query(
            "more_like_this",
            fields=["job_description"],
            like=profile_text["about_me"],
            min_term_freq=1,
            min_doc_freq=0,
        )
        r = s.execute()
        score_components["about_me"] = r.hits.max_score or 0
    else:
        score_components["about_me"] = 0

    # -----------------------------
    # 3. Work Type match
    # -----------------------------
    score_components["work_type"] = fuzzy_list_match(
        profile_text["work_type"], job_text["work_type"]
    )

    # -----------------------------
    # 4. Location match
    # -----------------------------
    score_components["location"] = fuzzy_list_match(
        profile_text["location"], job_text["location"]
    )

    # -----------------------------
    # 5. Employment Type
    # -----------------------------
    score_components["employment"] = fuzzy_list_match(
        profile_text["employment"], job_text["employment"]
    )

    # -----------------------------
    # Normalize scores into 0–100
    # -----------------------------
    final = 0
    for key, weight in WEIGHTS.items():
        comp_score = score_components.get(key, 0)

        # ES similarity scores may vary (0–10), so normalize to 0–1
        if comp_score > 1:
            comp_score = min(comp_score / 10, 1)

        final += comp_score * weight

    # max possible = sum(weights)
    max_possible = sum(WEIGHTS.values())
    normalized = (final / max_possible) * 100

    return round(normalized, 2)
