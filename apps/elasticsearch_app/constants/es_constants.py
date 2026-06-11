FILTER_FIELDS = {
    "title": {"path": "title.raw", "nested": False},
    "job_description": {"path": "job_description.raw", "nested": False},
    "remote_type": {"path": "remote_type.raw", "nested": False},
    "location": {"path": "location.raw", "nested": False},
    "job_level": {"path": "job_level.raw", "nested": False},
    "time_type": {"path": "time_type.raw", "nested": False},
    "category": {"path": "category.raw", "nested": False},

    # nested
    "company.id": {"path": "company.id", "nested": True, "nested_path": "company"},

    # salary fields (flat numeric)
    "salary_min": {"path": "salary_min", "nested": False},
    "salary_max": {"path": "salary_max", "nested": False},

    # salary currency
    "salary_currency": {"path": "salary_currency", "nested": False},

    # nested additional_field
    "additional_field.name": {
        "path": "additional_field.name.raw",
        "nested": True,
        "nested_path": "additional_field",
    },
    "additional_field.field_name": {
        "path": "additional_field.field_name.raw",
        "nested": True,
        "nested_path": "additional_field",
    },
}

ORDERING_FIELDS = {
    "create_date": "create_date",
    "post_date": "post_date",
    "expire_date": "expire_date",
}

# Global search fields for company, job, and people.
COMPANY_SEARCH_FIELDS = ["name^3", "industry"]

JOB_SEARCH_FIELDS = ["title^4", "job_description", "job_requirement", "company_name"]

PEOPLE_SEARCH_FIELDS = ["full_name^3", "current_position", "company_name"]