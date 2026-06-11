def dedup_key_user(user_company_profile_id, activity_type, job_post_id):
    return f"user:{user_company_profile_id}:{activity_type}:{job_post_id}"


def dedup_key_anon(anon_id, activity_type, job_post_id):
    return f"anonymous:{anon_id}:{activity_type}:{job_post_id}"


def redis_counter_key(activity_type, job_post_id):
    return f"job_activity:{activity_type}:{job_post_id}"
