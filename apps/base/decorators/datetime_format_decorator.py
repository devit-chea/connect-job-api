from functools import wraps
from enum import Enum
from datetime import datetime
from django.conf import settings
from zoneinfo import ZoneInfo


class DateTimeFormat(Enum):
    DEFAULT = "%Y-%m-%d %H:%M:%S"
    SHORT_DATE = "%d-%m-%Y"
    LONG_DATE = "%A, %d %B %Y"
    ISO_DATE = "%Y-%m-%d"
    TIME_ONLY = "%H:%M:%S"
    ABBR_DATE = "%d %b %Y"


def datetime_format_decorator(
    date_format=DateTimeFormat.DEFAULT,
    fields=None,
    field_formats=None,
    use_timezone=False,
):
    """
    Decorator for DRF serializers to format date/datetime fields.

    :param date_format: Default datetime format (str or Enum)
    :param fields: Optional list of fields (supports nested, e.g. "created_by.date_joined")
    :param field_formats: Optional dict of field-specific formats
    :param use_timezone: Whether to convert to local timezone (uses settings.TIME_ZONE or UTC)
    """
    local_tz = ZoneInfo(settings.TIME_ZONE)  # Replaces pytz.timezone

    def decorator(cls):
        original_to_representation = cls.to_representation

        @wraps(original_to_representation)
        def new_to_representation(self, instance):
            data = original_to_representation(self, instance)

            fmt_default = (
                date_format.value if isinstance(date_format, Enum) else date_format
            )
            date_fields = (
                fields
                if fields is not None
                else getattr(self.Meta, "date_format_fields", [])
            )
            formats = field_formats or {}

            for field_path in date_fields:
                parts = field_path.split(".")
                current = data

                try:
                    # Drill into nested dicts if needed
                    for part in parts[:-1]:
                        current = current.get(part)
                        if not isinstance(current, dict):
                            raise ValueError(f"Invalid nested field path: {field_path}")

                    field = parts[-1]

                    if field not in current:
                        continue

                    raw_value = current.get(field)
                    if not raw_value:
                        continue

                    # Convert string → datetime
                    if isinstance(raw_value, datetime):
                        dt = raw_value
                    else:
                        value = raw_value.replace("Z", "+00:00")
                        dt = datetime.fromisoformat(value)

                    # --- TIMEZONE HANDLING via zoneinfo ---
                    if use_timezone:
                        # If naive → assume UTC first
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

                        # Convert UTC → local timezone
                        dt = dt.astimezone(local_tz)

                    # Determine correct format
                    fmt_used = formats.get(field_path, fmt_default)
                    fmt_used = (
                        fmt_used.value if isinstance(fmt_used, Enum) else fmt_used
                    )
                    # Apply formatting
                    current[field] = dt.strftime(fmt_used)

                except Exception:
                    continue

            return data

        cls.to_representation = new_to_representation
        return cls

    return decorator
