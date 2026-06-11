def flatten_job_preference(preference) -> str:
    """
    Flattens an InnerDoc or dict into a plain string for similarity matching.
    """
    flat_parts = []

    # Convert InnerDoc to plain dict if needed
    if hasattr(preference, "to_dict"):
        preference = preference.to_dict()

    if not isinstance(preference, dict):
        return ""

    for key, value in preference.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat_parts.append(f"{sub_key} {sub_value}")
        elif isinstance(value, (list, tuple)):
            flat_parts.append(f"{key} " + " ".join(map(str, value)))
        else:
            flat_parts.append(f"{key} {value}")

    return " ".join(flat_parts)
