def get_jwt_claims(auth):
    if hasattr(auth, "payload"):
        return auth.payload or {}
    if isinstance(auth, dict):
        return auth
    return {}

def get_user_company_profile_id(auth):
    claims = get_jwt_claims(auth)
    return claims.get("user_company_profile_id")
