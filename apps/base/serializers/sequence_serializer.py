from rest_framework import serializers
from drf_writable_nested.serializers import WritableNestedModelSerializer

from apps.base.models.company_model import Company
from apps.base.models.sequence_model import Sequence, SequenceDateRange
from apps.base.mixins.sequence_mixin import SequenceMixin
from apps.base.serializers.base_serializer import BaseSerializer

RESET_TYPE_PARAMETERS = ["%YEARS", "%MONTHS", "%DAYS", "%YEAR", "%MONTH", "%DAY"]


def _check_required_parameter(value, parameters: list):
    result = []
    for i in parameters:
        if i in value:
            result.append(i)

    return result


class SequenceDateRangeSerializer(BaseSerializer, SequenceMixin):
    preview = serializers.SerializerMethodField()

    class Meta:
        model = SequenceDateRange
        fields = "__all__"
        read_only_fields = ["sequence"]

    def validate(self, value):
        _message = {}

        custom_fields = ""

        if "prefix" in value and value["prefix"] is not None:
            custom_fields += value["prefix"]

        if "suffix" in value and value["suffix"] is not None:
            custom_fields += value["suffix"]

        reset_type = value["reset_type"] if "reset_type" in value else "manual"

        match reset_type:
            case "yearly":
                parameters = ["YEAR"]
                if len(_check_required_parameter(custom_fields, parameters)) < len(
                    parameters
                ):
                    _message["prefix"] = _message["suffix"] = [
                        "Prefix or Suffix should contain parameters (%YEAR)"
                    ]

            case "monthly":
                parameters = ["YEAR", "MONTH"]
                if len(_check_required_parameter(custom_fields, parameters)) < len(
                    parameters
                ):
                    _message["prefix"] = _message["suffix"] = [
                        "Prefix or Suffix should contain parameters (%YEAR, %MONTH)"
                    ]

            case "daily":
                parameters = ["YEAR", "MONTH", "DAY"]
                if len(_check_required_parameter(custom_fields, parameters)) < len(
                    parameters
                ):
                    _message["prefix"] = _message["suffix"] = [
                        "Prefix or Suffix should contain parameters (%YEAR, %MONTH, %DAY)"
                    ]

        if "start_number" and "next_number" and "increment_number" in value:
            if not (
                value["next_number"]
                >= (value["increment_number"] + value["start_number"])
            ):
                _message["next_number"] = [
                    "Next number should be a number after start number increased!"
                ]
            if (
                "end_number" in value
                and not value["end_number"] == 0
                and not value["end_number"] is None
                and not (value["end_number"] > value["next_number"])
            ):
                _message["end_number"] = [
                    "End number should be greater than next number!"
                ]

        if not _message == {}:
            raise serializers.ValidationError(_message)

        return value

    def validate_increment_number(self, value):
        if value == 0:
            raise serializers.ValidationError("Increase number should bigger than 0")
        return value


class SequenceCompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ["id", "name"]


class SequenceSerializer(WritableNestedModelSerializer, SequenceMixin):
    sequence_date_ranges = SequenceDateRangeSerializer(many=True)

    class Meta:
        model = Sequence
        fields = "__all__"


class SequenceReadOnlySerializer(serializers.ModelSerializer, SequenceMixin):
    next_number = serializers.SerializerMethodField()
    sequence_date_ranges = SequenceDateRangeSerializer(many=True, read_only=True)

    class Meta:
        model = Sequence
        fields = "__all__"
        depth = 1


class SequencePreviewSerializer(serializers.Serializer):
    padding = serializers.IntegerField(default=0)
    prefix = serializers.CharField(max_length=255)
    next_number = serializers.IntegerField(default=1)
    suffix = serializers.CharField(max_length=255)
