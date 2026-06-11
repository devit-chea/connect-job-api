from rest_framework.validators import UniqueTogetherValidator, qs_filter, qs_exists
from django.utils.translation import gettext_lazy as _

from apps.core.exceptions.base_exceptions import (
    BadRequestException,
    BaseException as InternalErrorException,
)
from apps.base.models.abstract_model import AbstractBaseCompany


class BaseUniqueTogetherValidator(UniqueTogetherValidator):
    message = _("This combination of ({field_names}) is already exist in {model_name}.")

    def __init__(
        self,
        queryset,
        fields: dict,
        **kwargs,
    ):
        message = kwargs.pop("message", None)
        self.custom_queryset = kwargs.pop("custom_queryset", None)
        self.is_current_company = kwargs.pop("is_current_company", True)
        self.custom_filter_kwarg = kwargs.pop("custom_filter_kwarg", {})
        self.exception_instance = kwargs.pop("exception_instance", None)

        super().__init__(queryset, fields.keys(), message)
        self.fields_with_lookup_filter = fields

    def filter_queryset(self, attrs, queryset, serializer):
        """
        Filter the queryset to all instances matching the given attributes.
        """
        # field names => field sources
        field_and_sources = [
            (field_name, serializer.fields[field_name].source)
            for field_name in self.fields
        ]

        # If this is an update, then any unprovided field should
        # have it's value set based on the existing instance attribute.
        if serializer.instance is not None:
            for field_name, source in field_and_sources:
                if source not in attrs:
                    attrs[source] = getattr(serializer.instance, source)

        # Determine the filter keyword arguments and filter the queryset.
        filter_kwargs = {
            f"{source}{self.fields_with_lookup_filter[field_name]}": self._strip_if_str(
                attrs, source
            )
            for field_name, source in field_and_sources
        }

        queryset = self._apply_custom_queryset(queryset, attrs, serializer)

        self._add_custom_filter_kwargs(filter_kwargs, attrs, serializer)

        self._add_company_filter_if_need(filter_kwargs, queryset, serializer)

        return qs_filter(queryset, **filter_kwargs)

    def _strip_if_str(self, attrs, source):
        return (
            attrs[source].strip() if isinstance(attrs[source], str) else attrs[source]
        )

    def __call__(self, attrs, serializer):
        self.enforce_required_fields(attrs, serializer)
        queryset = self.queryset
        queryset = self.filter_queryset(attrs, queryset, serializer)
        queryset = self.exclude_current_instance(attrs, queryset, serializer.instance)

        # Ignore validation if any field is None
        checked_values = [
            value for field, value in attrs.items() if field in self.fields
        ]
        if None not in checked_values and qs_exists(queryset):
            if self.exception_instance:
                raise self.exception_instance

            field_names = ", ".join(self.fields)
            message = self.message.format(
                field_names=field_names, model_name=queryset.model.__name__
            )
            raise BadRequestException([message])

    def _apply_custom_queryset(self, queryset, attrs, serializer):
        if self.custom_queryset:
            serializer_func = getattr(serializer, self.custom_queryset, None)
            queryset = serializer_func(attrs, queryset)

        return queryset

    def _add_custom_filter_kwargs(self, filter_kwargs, attrs, serializer):
        for key, serializer_func_name in self.custom_filter_kwarg.items():
            serializer_func = getattr(serializer, serializer_func_name, None)
            if not serializer_func:
                raise InternalErrorException(
                    f"Invalid method:{serializer_func_name} in {serializer.__class__.__name__}"
                )

            value = serializer_func(attrs)
            filter_kwargs[key] = value

    def _add_company_filter_if_need(self, filter_kwargs, queryset, serializer):
        request = serializer.context.get("request")
        if (
            self.is_current_company
            and request
            and issubclass(getattr(queryset, "model", None), AbstractBaseCompany)
        ):
            filter_kwargs["company"] = request.user.base_company
