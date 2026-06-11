from django.utils import timezone
from rest_framework import serializers

from apps.base.utils.sequence_utils import generate_sequence_number


class SequenceNumberMixin:
    """
    Mixin for ModelSerializer that auto-generates a sequence number on create.

    How to use
    ----------
    1. Add this mixin BEFORE ModelSerializer in the MRO.
    2. Define a `sequence_config` dict on the serializer class (see fields below).
    3. Make the number field  required=False, allow_blank=True  in the serializer.
    4. Keep your ViewSet as a plain ModelViewSet — no custom create() needed.

    sequence_config keys
    --------------------
    number_field  (str, required)
        The model field that stores the sequence number. e.g. "pipeline_number"

    prefix        (str, default "")
        Text before the numeric part.  e.g. "PIP"

    suffix        (str | callable, default "")
        Text after the numeric part.  Pass a callable (no args) for dynamic
        values, e.g.  lambda: f"-{timezone.now().year}"

    separator     (str, default "-")
        Placed between prefix/number and number/suffix.

    padding       (int, default 3)
        Minimum digit width (zero-padded).

    scope_fields  (list[str], default ["company_id"])
        Model fields used to build the scope filter for the counter.
        Values are read from the validated data OR from request.
        E.g. ["company_id"] builds {"company_id": <user.company_id>}
             ["company_id", "year"] builds {"company_id": ..., "year": ...}

    scope_source  (str, default "user")
        Where to resolve scope_fields values from:
          "user"       → getattr(request, field)
          "data"       → validated_data[field]   (client must supply it)
          "mixed"      → try validated_data first, fall back to request
    """

    sequence_config: dict = {}

    def _resolve_scope_filters(self, validated_data: dict) -> dict:
        cfg = self.sequence_config
        scope_fields = cfg.get("scope_fields", ["company_id"])
        scope_source = cfg.get("scope_source", "user")
        request = self.context.get("request")

        filters = {}
        for field in scope_fields:
            if scope_source == "data":
                filters[field] = validated_data[field]
            elif scope_source == "user":
                filters[field] = getattr(request, field)
            else:  # "mixed"
                filters[field] = validated_data.get(field) or getattr(request, field)
        return filters

    def _resolve_suffix(self) -> str:
        suffix = self.sequence_config.get("suffix", "")
        return suffix() if callable(suffix) else suffix

    def create(self, validated_data: dict):
        cfg = self.sequence_config
        number_field = cfg.get("number_field")

        if number_field and not validated_data.get(number_field):
            # No custom number supplied — generate one.
            scope_filters = self._resolve_scope_filters(validated_data)
            validated_data[number_field] = generate_sequence_number(
                model_class=self.Meta.model,
                number_field=number_field,
                scope_filters=scope_filters,
                prefix=cfg.get("prefix", ""),
                suffix=self._resolve_suffix(),
                separator=cfg.get("separator", "-"),
                padding=cfg.get("padding", 3),
            )

        return super().create(validated_data)
