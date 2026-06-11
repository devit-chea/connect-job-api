from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers
from datetime import datetime
from django.db.models.query import QuerySet
from django.contrib.auth.models import Group
from django.db import transaction


from apps.base.models.sequence_model import Sequence, SequenceDateRange
from apps.base.utils import base_util


class SequenceMixin:
    message = "The reference-no number is not config"
    

    def get_sequence_numbering(self, _model_instance):
        sequence_instance = self._get_sequence_by_contenttype(_model_instance)
        active_sequence = self._get_active_sequence(sequence_instance, _model_instance)
        if not active_sequence:

            raise serializers.ValidationError(self.message)
        if (
            active_sequence.end_number > 0
            and active_sequence.end_number < active_sequence.next_number
        ):

            raise serializers.ValidationError(
                "The reference-no number is reach the limitation"
            )

        return self._map_next_number(active_sequence)

    @transaction.atomic()
    def get_sequence_numbering_custom(self, _model_instance):
        sequence_instance = self._get_sequence_by_contenttype(_model_instance)
        active_sequence = self._get_active_sequence(sequence_instance, _model_instance)
        if not active_sequence:
            raise serializers.ValidationError(self.message)
        if (
            active_sequence.end_number > 0
            and active_sequence.end_number < active_sequence.next_number
        ):
            raise serializers.ValidationError(
                "The reference-no number is reach the limitation"
            )

        active_sequence_locked = (
            SequenceDateRange.objects.select_for_update()
            .filter(pk=active_sequence.pk)
            .first()
        )
        return active_sequence_locked, self._map_next_number(active_sequence_locked)

    def get_sequence_numbering_related(self, _model_instance):
        sequence_instance = self._get_sequence_by_contenttype_related(_model_instance)
        active_sequence = self._get_active_sequence(sequence_instance, _model_instance)
        if not active_sequence:
            # remove the object with empty numbering
            _model_instance.delete()

            raise serializers.ValidationError(self.message)
        if (
            active_sequence.end_number > 0
            and active_sequence.end_number < active_sequence.next_number
        ):
            # remove the object with empty numbering
            _model_instance.delete()

            raise serializers.ValidationError(
                "The Reference-no number is reach the limitation"
            )
        # self.increment_sequence_numbering_related(_model_instance)

        active_sequence_locked = (
            SequenceDateRange.objects.select_for_update()
            .filter(pk=active_sequence.pk)
            .first()
        )
        return active_sequence_locked, self._map_next_number(active_sequence_locked)

    def increment_sequence_numbering_related(self, active_sequence):
        return self._increment(active_sequence)

    def increment_sequence_numbering_custom(self, active_sequence):
        return self._increment(active_sequence)

    def increment_sequence_numbering(self, _model_instance):
        sequence_instance = self._get_sequence_by_contenttype(_model_instance)
        active_sequence = self._get_active_sequence(sequence_instance, _model_instance)
        return self._increment(active_sequence)

    def get_next_number(self, sequence_instance):
        active_sequence = self._get_active_sequence(sequence_instance)
        if not active_sequence:
            return None
        if (
            active_sequence.end_number > 0
            and active_sequence.end_number < active_sequence.next_number
        ):
            return None
        return self._map_next_number(active_sequence)

    def get_preview(self, obj):
        return self._map_next_number(obj)

    def reset_sequences(self):
        sequences = Sequence.objects.exclude(reset_type="manual").all()
        for sequence in sequences:
            active_sequence = self._get_active_sequence(sequence)
            if active_sequence:
                if sequence.reset_type == "yearly" and base_util.is_new_year():
                    self._replicated(
                        active_sequence, base_util.is_new_year(get_date=True)
                    )
                elif sequence.reset_type == "monthly" and base_util.is_new_month():
                    self._replicated(
                        active_sequence, base_util.is_new_month(get_date=True)
                    )
                else:
                    self._replicated(active_sequence, base_util.get_date_format())

    def sequence_preview(self, request):
        prefix = self._map_format(request.data.get("prefix"))
        suffix = self._map_format(request.data.get("suffix"))
        next_number = self._map_padding(
            request.data.get("next_number"), request.data.get("padding")
        )
        return str(prefix) + str(next_number) + str(suffix)

    def _replicated(self, active_sequence, start_date):
        active_start_date = datetime.combine(
            active_sequence.start_date, datetime.min.time()
        )
        start_date = datetime.strptime(start_date, "%Y-%m-%d")
        if active_start_date < start_date:
            active_sequence.pk = None
            active_sequence.start_date = start_date
            active_sequence.next_number = active_sequence.start_number
            active_sequence.save()

    def _get_sequence_by_contenttype_related(self, model_instance):
        # case group model custom create serializer
        if isinstance(model_instance, dict):
            model_instance = Group.objects.get(id=model_instance.get("id", None))

        # find model class content_type
        model_content = ContentType.objects.get(
            app_label=model_instance._meta.app_label,
            model=model_instance._meta.model_name,
        )
        # find sequence object related content_type
        sequence_instance = Sequence.objects.filter(
            content_type_id=model_content.id,
            company=self.context.get("request").user.base_company,
        )
        return sequence_instance.all()

    def _get_sequence_by_contenttype(self, model_instance):
        # case group model custom create serializer
        if isinstance(model_instance, dict):
            model_instance = Group.objects.get(id=model_instance.get("id", None))

        # find model class content_type
        model_content = ContentType.objects.get(
            app_label=model_instance._meta.app_label,
            model=model_instance._meta.model_name,
        )
        # find sequence object related content_type
        sequence_instance = Sequence.objects.filter(
            content_type_id=model_content.id, company=self.request.user.base_company
        )
        return sequence_instance.all()

    def _map_next_number(self, active_sequence):
        prefix = self._map_format(active_sequence.prefix)
        suffix = self._map_format(active_sequence.suffix)
        next_number = self._map_padding(
            active_sequence.next_number, active_sequence.padding
        )
        return prefix + next_number + suffix

    def _get_active_sequence(self, sequence_obj, _model_instance=None):
        sequence_date_range_objs = (
            SequenceDateRange.objects.filter(
                active=True,
                start_date__lte=base_util.get_date_format(),
            )
            .exclude(end_date__lte=base_util.get_date_format())
            .order_by("create_date")
        )
        if isinstance(sequence_obj, QuerySet):
            sequence_date_range_objs = sequence_date_range_objs.filter(
                sequence__in=sequence_obj
            )
        else:
            sequence_date_range_objs = sequence_date_range_objs.filter(
                sequence=sequence_obj
            )

        if sequence_date_range_objs:
            for sequence_date_range in sequence_date_range_objs:
                conditions = self._conditions(_model_instance, sequence_date_range)
                if conditions:
                    return sequence_date_range
            return sequence_date_range_objs.filter(field_name=None).last()

    def _conditions(self, _model_instance, sequence_date_range):
        """_summary_
            return true if all request data match with all conditions otherwise false will return
        Args:
            _model_instance (_type_): model object
            condition_fields (_type_): field with condition
        """
        if _model_instance is None:
            return False
        if sequence_date_range.field_name is None:
            return False

        # get object field value with foreign key name field
        _model_field_value = getattr(_model_instance, sequence_date_range.field_name)
        _model_field = _model_instance._meta.get_field(sequence_date_range.field_name)
        if _model_field.get_internal_type() == "ForeignKey":
            if hasattr(_model_field_value, "name"):
                _model_field_value = _model_field_value.name

        # compare field
        if _model_field_value == sequence_date_range.field_value:
            return True
        return False

    def _map_format(self, text: str):
        YEARS = base_util.get_date_format(str_format="%Y")
        MONTHS = base_util.get_date_format(str_format="%m")
        DAYS = base_util.get_date_format(str_format="%d")
        YEAR = base_util.get_date_format(str_format="%y")
        MONTH = MONTHS.replace("0", "")
        DAY = DAYS.replace("0", "")
        format_obj = {
            "%YEARS": YEARS,
            "%MONTHS": MONTHS,
            "%DAYS": DAYS,
            "%YEAR": YEAR,
            "%MONTH": MONTH,
            "%DAY": DAY,
        }
        return base_util.replace_multi_strings(text, format_obj)

    def _map_padding(self, number, padding):
        number = 0 if not number else int(number)
        padding = 0 if not padding else int(padding)
        return str(number).rjust(padding, "0")

    def _increment(self, active_sequence):
        active_sequence.next_number = (
            active_sequence.next_number + active_sequence.increment_number
        )
        active_sequence.save()
        
