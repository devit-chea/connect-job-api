class ConnectorStatus:
    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    REVOKED = "revoked"
    SUSPENDED = "suspended"

    CHOICES = (
        (ACTIVE, "Active"),
        (DISCONNECTED, "Disconnected"),
        (REVOKED, "Revoked"),
        (SUSPENDED, "Suspended"),
    )


# Pre-defined field mappings seeded automatically when a new integration is
# established. Each tuple is:
#   (source_field, target_field, mapping_type, default_value)
#
# source_field  = ConnectJob InboundJobPostSerializer field name
# target_field  = Wing Digital / ERP field name (can be updated by the admin)
# mapping_type  = "free" (direct copy) | "mapped" (has value-level mappings)
# default_value = value used when the ERP omits the field entirely (None = no default)
#
# Users see these on the Data Mapping page and can edit target_field,
# default_value, add value-mappings, or delete rows they don't need.
DEFAULT_FIELD_MAPPINGS = [
    # ── Core job fields ────────────────────────────────────────────────────────
    ("title",               "position",          "free",   None),
    ("job_code",            "job_code",           "free",   None),
    ("job_description",     "description",        "free",   None),
    ("job_requirement",     "requirements",       "free",   None),
    ("job_responsibility",  "responsibilities",   "free",   None),
    ("benefits",            "benefits",           "free",   None),

    # ── Classification ─────────────────────────────────────────────────────────
    # mapping_type "mapped" → admin should add value-level mappings for categories
    ("category",            "job_category",       "mapped", None),
    ("job_level",           "job_level",          "free",   None),
    ("time_type",           "job_type",           "free",   None),
    ("contract_type",       "employment_type",    "free",   None),
    ("remote_type",         "remote_type",        "free",   None),

    # ── Location ───────────────────────────────────────────────────────────────
    ("location",            "department_code",    "free",   None),

    # ── Salary ─────────────────────────────────────────────────────────────────
    ("salary_min",          "min_salary",         "free",   None),
    ("salary_max",          "max_salary",         "free",   None),
    ("salary_type",         "salary_type",        "free",   "NEGOTIABLE"),
    ("salary_currency",     "currency",           "free",   "USD"),

    # ── Headcount & dates ──────────────────────────────────────────────────────
    ("hire_no",             "no_of_positions",    "free",   "1"),
    ("expire_date",         "expire_date",        "free",   None),
    ("year_of_experience",  "experience_years",   "free",   None),
]
