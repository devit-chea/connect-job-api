from apps.activity_tracking_app.models.job_post_user_state_model import (
    JobPostUserStateModel,
)
from apps.auth_oauth.constants.auth_constants import UserTypes
from apps.auth_oauth.models.profile_model import Profile
from apps.base.utils.file_management_util import FileURLService
from apps.elasticsearch_app.queries.applicant_query import build_es_recommend_applicant_query
from apps.elasticsearch_app.search.applicant_profile_document import (
    ApplicantProfileDocument,
)
from elasticsearch_dsl import Q, Search
from elasticsearch_dsl.connections import connections

from apps.elasticsearch_app.selectors.job_post_user_state_selector import (
    search_by_fullname,
)
from apps.elasticsearch_app.services.job_matching_service import (
    calculate_similarity_score,
)

es_client = connections.get_connection()


class MockProfile:
    def __init__(self, profile_id, cover_id):
        self.profile_picture_id = profile_id
        self.cover_picture_id = cover_id


# Using constants for clarity, proportional to the required weights (60:30:10)
WEIGHT_REQUIREMENTS = 6.0
WEIGHT_RESPONSIBILITIES = 3.0
WEIGHT_DESCRIPTION = 1.0


def get_match_category(score):
    if score >= 80:
        return "green"
    elif score >= 50:
        return "yellow"
    else:
        return "red"


def get_matching_applicants_with_scores(
    job_post,
    min_score_threshold=1,
    query_string=None,
    filters=None,
    page_size=None,
    offset=0,
    is_job_state=True,
):
    """
    Retrieves matching applicants from Elasticsearch with scores, applying
    pagination directly to the ES query.

    :param page_size: Page size (number of results to return).
    :param offset: Starting point for results (page number * page size).
    """

    # --- STEP 1: Get IDs of Applied Applicants from the Database (UNCHANGED) ---
    if is_job_state is False:
        get_profile_records = Profile.objects.filter(
            profile_type=UserTypes.APPLICANT.value
        )
    else:
        get_profile_records = JobPostUserStateModel.objects.filter(
            job_post=job_post,
            status="applied",
            # user_company_profile__profile__status=ProfileStatus.ACTIVE
        ).select_related("user_company_profile__profile")

    filtered_applicants = get_profile_records

    if query_string:
        filtered_applicants = search_by_fullname(query_string, filtered_applicants)

    if not is_job_state:
        # If filtered_applicants is a QuerySet of Profile objects
        applied_profile_ids = list(filtered_applicants.values_list("id", flat=True))
    else:
        # If filtered_applicants is a QuerySet of JobPostUserStateModel objects
        applied_profile_ids = [
            state.user_company_profile.profile.id
            for state in filtered_applicants
            if state.user_company_profile and state.user_company_profile.profile
        ]

    if not applied_profile_ids:
        return [], 0

    id_filter = Q("terms", id=applied_profile_ids)

    # --- STEP 2: Build the Weighted Elasticsearch Query ---

    # We use a 'bool' query to combine the three weighted criteria using 'should'
    # and a high 'minimum_should_match' to ensure candidates meet some requirement.

    # 1. Job Requirements (60% Weight)
    # Target fields: Skills (most direct match), Education, Total Experience (handled by function_score below)
    requirements_query = Q(
        "multi_match",
        query=job_post.job_requirement or "",
        fields=[
            "skills_list^2",  # Higher boost for direct skills
            "educations.degree^1.5",  # Education relevance
            "educations.study_field^1.5",
            # Note: Total Experience is handled separately in function_score for structure
        ],
        type="best_fields",
        boost=WEIGHT_REQUIREMENTS,  # Apply the 6.0 boost
    )

    # 2. Responsibilities (30% Weight)
    # Target fields: Applicant's past job titles and descriptions
    responsibilities_query = Q(
        "multi_match",
        query=job_post.job_responsibility or "",
        fields=[
            "work_experiences.job_title^1.5",
            "work_experiences.job_description",
        ],
        type="best_fields",
        boost=WEIGHT_RESPONSIBILITIES,  # Apply the 3.0 boost
    )

    # 3. Job Description/Culture/Keywords (10% Weight)
    # Target fields: General keywords in applicant's 'about_me' and general profile
    description_query = Q(
        "multi_match",
        query=job_post.job_description or "",
        fields=[
            "about_me",
        ],
        type="best_fields",
        boost=WEIGHT_DESCRIPTION,  # Apply the 1.0 boost
    )

    # Combine the three weighted queries into one main query
    main_bool_query = Q(
        "bool",
        should=[requirements_query, responsibilities_query, description_query],
        # Ensure a match on at least one criteria to be scored
        minimum_should_match=1,
    )

    # --- STEP 3: Implement Structured Boost (Job Experience) ---

    # Use a function_score query to apply the Experience score on top of the text matching.
    # We wrap the main_bool_query in function_score.
    functions = [
        {
            "gauss": {
                "job_experience_years": {
                    "origin": 5.0,  # Ideal experience is 5 years
                    "scale": 2.0,  # Score drops by 50% within 2 years of origin
                    "offset": 0.0,
                    "decay": 0.5,
                }
            },
            # Increase weight to emphasize structured experience match
            "weight": 10,
        }
    ]

    # Combine the main query with function score
    function_score_query = Q(
        "function_score",
        query=main_bool_query,
        functions=functions,
        score_mode="sum",  # Sum the original score and function boosts
        min_score=min_score_threshold,
    )

    # --- STEP 4: Execute Search with ID Filter, Pagination, and Normalization ---

    s = Search(using=es_client, index=ApplicantProfileDocument.Index.name)
    s = s.query("bool", filter=[id_filter], must=[function_score_query])

    # Apply pagination and sorting directly to the Elasticsearch query
    s = s.sort({"_score": {"order": "desc"}})
    s = s[
        offset : offset + (page_size or len(applied_profile_ids))
    ]  # Use offset and page_size

    response = s.execute()

    # Get the total count of documents that matched the query *before* pagination
    total_count = (
        response.hits.total.value
        if hasattr(response.hits.total, "value")
        else response.hits.total
    )

    # Normalization: Find max score from the current page and convert to 0-100%
    max_score = max((hit.meta.score for hit in response), default=1)

    results = []
    for hit in response:
        # Calculate percentage: (actual_score / max_score) * 100
        percentage_score = min(100, round((hit.meta.score / max_score) * 100))

        profile_data = MockProfile(
            profile_id=hit.profile_picture_id,
            cover_id=None,
        )
        presentation = FileURLService.present_profile_images(profile_data)
        profile_picture_data = presentation.get("profile_image")
        file_path = None
        if isinstance(profile_picture_data, dict):
            file_path = profile_picture_data.get("file_path")

        results.append(
            {
                "applicant_profile_id": hit.id,
                "current_position": hit.current_position,
                "location_name": hit.location_name,
                "phone_number": hit.phone_number,
                "full_name": hit.full_name,
                "percentage_score": percentage_score,
                "score_category": get_match_category(percentage_score),
                "profile_picture_url": file_path,
            }
        )

    return results, total_count


def get_applicant_score(job_post, profile_id, *args, **kwargs):
    """
    Calculates the raw Elasticsearch score for a single applicant profile
    against a specific job post.

    Args:
        job_post: The JobPost model instance.
        profile_id (int/str): The ID of the ApplicantProfileDocument (Profile model ID).

    Returns:
        float: The raw Elasticsearch score, or 0.0 if no match is found.
    """

    # We use 'terms' just like before, but with only one ID.
    try:
        # Ensure profile_id is an integer if your model IDs are integers
        single_profile_id = int(profile_id)
    except (ValueError, TypeError):
        # Handle cases where profile_id might be invalid
        return 0.0

    id_filter = Q("term", id=single_profile_id)

    function_score_query = build_es_recommend_applicant_query(job_post, 1)

    s = Search(using=es_client, index=ApplicantProfileDocument.Index.name)
    # Apply the ID filter and the scoring query
    s = s.query("bool", filter=[id_filter], must=[function_score_query])
    s = s.params(size=1)  # Only need one result

    response = s.execute()

    # Check if a hit was returned and extract the raw score
    if response and response.hits:
        # Return the raw score of the first (and only) hit
        return response.hits[0].meta.score
    else:
        return 0.0


def _get_applied_applicant_ids(job_post, query_string, is_job_state):
    """
    Step 1: Retrieves the profile IDs of applicants based on job state and optional search query.
    """
    if is_job_state is False:
        get_profile_records = Profile.objects.filter(
            profile_type=UserTypes.APPLICANT.value,
        )[:200]
    else:
        get_profile_records = JobPostUserStateModel.objects.filter(
            job_post=job_post,
            status="applied",
        ).select_related("user_company_profile__profile")[:200]

    filtered_applicants = get_profile_records

    if query_string:
        filtered_applicants = search_by_fullname(query_string, filtered_applicants)

    if not is_job_state:
        # If filtered_applicants is a QuerySet of Profile objects
        applied_profile_ids = list(filtered_applicants.values_list("id", flat=True))
    else:
        # If filtered_applicants is a QuerySet of JobPostUserStateModel objects
        applied_profile_ids = [
            state.user_company_profile.profile.id
            for state in filtered_applicants
            if state.user_company_profile and state.user_company_profile.profile
        ]

    return applied_profile_ids


def _process_search_results(response, job_post):
    """
    Step 4: Builds final results and computes custom similarity score.
    """
    results = []

    for hit in response:

        # ----------------------------------------------------
        # 1. Load the relational Profile record from database
        # ----------------------------------------------------
        try:
            profile_doc = Profile.objects.get(id=hit.id)
        except Exception:
            continue

        # ----------------------------------------------------
        # 2. Apply your custom similarity scoring function
        # ----------------------------------------------------
        percentage_score = calculate_similarity_score(profile_doc, job_post)

        # ----------------------------------------------------
        # 3. Profile images (unchanged from your version)
        # ----------------------------------------------------
        profile_data = MockProfile(
            profile_id=hit.profile_picture_id,
            cover_id=None,
        )
        presentation = FileURLService.present_profile_images(profile_data)
        profile_picture_data = presentation.get("profile_image")

        file_path = None
        if isinstance(profile_picture_data, dict):
            file_path = profile_picture_data.get("file_path")

        # ----------------------------------------------------
        # 4. Append final combined record
        # ----------------------------------------------------
        results.append(
            {
                "applicant_profile_id": hit.id,
                "current_position": hit.current_position,
                "location_name": hit.location_name,
                "phone_number": hit.phone_number,
                "full_name": hit.full_name,
                "percentage_score": percentage_score,
                "score_category": get_match_category(percentage_score),
                "profile_picture_url": file_path,
            }
        )

    return results


def get_recommended_applicants(
    job_post,
    min_score_threshold=1,
    query_string=None,
    filters=None,  # This parameter was unused in original code, kept for signature consistency
    page_size=None,
    offset=0,
    is_job_state=True,
):
    """
    Main function to retrieve and score applicants for a job post.
    """
    applied_profile_ids = _get_applied_applicant_ids(
        job_post, query_string, is_job_state
    )

    if not applied_profile_ids:
        return [], 0

    id_filter = Q("terms", id=applied_profile_ids)

    function_score_query = build_es_recommend_applicant_query(job_post, min_score_threshold)

    s = Search(using=es_client, index=ApplicantProfileDocument.Index.name)
    s = s.query("bool", filter=[id_filter], must=[function_score_query])

    s = s.sort({"_score": {"order": "desc"}})

    effective_page_size = (
        page_size if page_size is not None else len(applied_profile_ids)
    )
    s = s[offset : offset + effective_page_size]

    response = s.execute()

    total_count = (
        response.hits.total.value
        if hasattr(response.hits.total, "value")
        else response.hits.total
    )

    results = _process_search_results(response, job_post)
    results = sorted(results, key=lambda x: x["percentage_score"], reverse=True)

    return results, total_count
