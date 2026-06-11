from rest_framework import serializers

from django.db.backends.postgresql.psycopg_any import NumericRange


class IntegerRangeField(serializers.Field):
    def to_internal_value(self, data):
        return NumericRange(data.get("lower"), data.get("upper"))

    def to_representation(self, value):
        return {"lower": value.lower, "upper": value.upper}
