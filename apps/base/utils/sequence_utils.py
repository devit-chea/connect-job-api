"""
utils/sequence_utils.py

A generic, reusable sequential-number generator for any Django model.

Features
--------
- Works with ANY model and ANY field — not tied to Pipeline.
- Customisable prefix, suffix, separator, and zero-padding width.
- Scoped by any filter (e.g. company_id, tenant_id, user_id, …).
- Handles user-supplied "custom" numbers gracefully:
    • Custom values are stored as-is and never overwritten.
    • The next auto-generated number is based on the highest
      numeric sequence found across ALL records (auto + custom),
      so the counter never goes backwards.
- Concurrency-safe via SELECT FOR UPDATE inside an atomic transaction.

Format examples (with defaults)
--------------------------------
    prefix="PIP",  separator="-", padding=3, suffix=""
        PIP-001, PIP-002, … PIP-999, PIP-1000

    prefix="INV",  separator="-", padding=4, suffix="-2025"
        INV-0001-2025, INV-0002-2025

    prefix="",     separator="",  padding=5, suffix=""
        00001, 00002, 00003

    prefix="ORD",  separator="_", padding=3, suffix=""
        ORD_001, ORD_002

Quickstart
----------
    from utils.sequence_utils import generate_sequence_number

    # Pipeline (scoped per company)
    number = generate_sequence_number(
        model_class   = Pipeline,
        number_field  = "pipeline_number",
        scope_filters = {"company_id": request.user.company_id},
        prefix        = "PIP",
    )
    # → "PIP-001"

    # Invoice (scoped per company, with year suffix)
    number = generate_sequence_number(
        model_class   = Invoice,
        number_field  = "invoice_number",
        scope_filters = {"company_id": request.user.company_id},
        prefix        = "INV",
        suffix        = f"-{timezone.now().year}",
        padding       = 4,
    )
    # → "INV-0001-2025"

    # Job (scoped per company)
    number = generate_sequence_number(
        model_class   = Job,
        number_field  = "job_number",
        scope_filters = {"company_id": request.user.company_id},
        prefix        = "JOB",
    )
    # → "JOB-001"
"""

from __future__ import annotations

import re
from typing import Any

from django.apps import apps
from django.db import models, transaction

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_sequence_number(
    *,
    model_class: type[models.Model] | str,
    number_field: str,
    scope_filters: dict[str, Any],
    prefix: str = "",
    suffix: str = "",
    separator: str = "-",
    padding: int = 3,
) -> str:
    """
    Generate the next sequential number for *any* Django model field.

    Parameters
    ----------
    model_class : Model class or "app_label.ModelName" string
        The Django model to query (e.g. Pipeline, or "pipelines.Pipeline").
    number_field : str
        The model field that stores the sequence number (e.g. "pipeline_number").
    scope_filters : dict
        ORM filter kwargs that define the scope/tenant boundary.
        E.g. {"company_id": 7}  or  {"company_id": 7, "year": 2025}
    prefix : str
        Text placed before the numeric part.  Default "".
    suffix : str
        Text placed after the numeric part.  Default "".
    separator : str
        Character(s) between prefix/number and number/suffix. Default "-".
        Set to "" for no separator.
    padding : int
        Minimum digits in the numeric part (zero-padded). Default 3.
        The number grows naturally beyond this width (no truncation).

    Returns
    -------
    str  — formatted sequence number, e.g. "PIP-001".

    Raises
    ------
    ValueError  — if scope_filters is empty or model_class cannot be resolved.
    """
    if not scope_filters:
        raise ValueError(
            "scope_filters must not be empty. "
            "Provide at least one field to scope the sequence (e.g. company_id)."
        )

    model = _resolve_model(model_class)

    with transaction.atomic():
        # Lock matching rows so concurrent requests queue up here instead of
        # racing to read the same "last" value.
        existing_values: list[str] = list(
            model.objects.select_for_update()
            .filter(**scope_filters)
            .values_list(number_field, flat=True)
        )

        # Find the highest numeric sequence across ALL records
        # (including any custom user-entered numbers).
        max_seq = _find_max_sequence(
            values=existing_values,
            prefix=prefix,
            suffix=suffix,
            separator=separator,
        )

        return _format_number(
            sequence=max_seq + 1,
            prefix=prefix,
            suffix=suffix,
            separator=separator,
            padding=padding,
        )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_model(model_class: type[models.Model] | str) -> type[models.Model]:
    """Accept either a Model class or an 'app_label.ModelName' string."""
    if isinstance(model_class, str):
        try:
            app_label, model_name = model_class.split(".")
            return apps.get_model(app_label, model_name)
        except (ValueError, LookupError) as exc:
            raise ValueError(
                f"Cannot resolve model from string {model_class!r}. "
                "Use 'app_label.ModelName' format."
            ) from exc
    return model_class


def _find_max_sequence(
    values: list[str],
    prefix: str,
    suffix: str,
    separator: str,
) -> int:
    """
    Scan all existing field values and return the highest integer sequence found.

    This handles three cases:
      1. Auto-generated values that match our format exactly  →  parsed normally.
      2. Custom user-entered values that partially match       →  we try to
         extract any trailing integer from them.
      3. Completely unparseable values                         →  skipped (0).

    The result is always the true maximum, so even if a user manually entered
    "PIP-050" the next auto number will be PIP-051, not PIP-006.
    """
    if not values:
        return 0

    max_seq = 0
    for value in values:
        seq = _extract_sequence(
            value, prefix=prefix, suffix=suffix, separator=separator
        )
        if seq > max_seq:
            max_seq = seq

    return max_seq


def _extract_sequence(
    value: str,
    prefix: str,
    suffix: str,
    separator: str,
) -> int:
    """
    Extract the leading integer from *value* after stripping prefix/suffix.

    Strategy (in order):
    1. Strip the known suffix from the end (if present).
    2. Strip the known prefix+separator from the start (if present).
    3. Read the leading digits of whatever remains.

    This is intentionally lenient so that user-supplied custom numbers like
    "PIP-042-CUSTOM" or "INV-99" still contribute their numeric part to the
    max-sequence calculation.
    """
    if not value:
        return 0

    working = value.strip()

    # Strip suffix (e.g. "-2025") from the right
    if suffix and working.endswith(suffix):
        working = working[: -len(suffix)]

    # Strip prefix+separator (e.g. "PIP-") from the left
    expected_prefix = f"{prefix}{separator}" if prefix else separator
    if expected_prefix and working.startswith(expected_prefix):
        working = working[len(expected_prefix) :]

    # Extract leading digits from whatever remains
    match = re.match(r"(\d+)", working)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            pass

    return 0


def _format_number(
    sequence: int,
    prefix: str,
    suffix: str,
    separator: str,
    padding: int,
) -> str:
    """
    Assemble the final formatted sequence string.

    Examples
    --------
    prefix="PIP", separator="-", padding=3, suffix=""    → "PIP-001"
    prefix="INV", separator="-", padding=4, suffix="-2025" → "INV-0001-2025"
    prefix="",    separator="",  padding=5, suffix=""    → "00001"
    """
    numeric_part = f"{sequence:0{padding}d}"

    parts: list[str] = []

    if prefix:
        parts.append(prefix)
        parts.append(separator)

    parts.append(numeric_part)

    if suffix:
        parts.append(suffix)

    return "".join(parts)
