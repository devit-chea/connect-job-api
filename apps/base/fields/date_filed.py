from rest_framework import serializers


class DateField(serializers.DateField):
    """
    DateFiled has attr allow_blank
    """

    def __init__(self, allow_blank=False, format=..., input_formats=None, **kwargs):
        self.allow_blank = allow_blank
        super().__init__(format, input_formats, **kwargs)

    def to_internal_value(self, value):
        if self.required and not value:
            self.fail("required")
        if self.allow_blank and not value:
            return None
        return super().to_internal_value(value)

    def to_representation(self, value):
        return value
