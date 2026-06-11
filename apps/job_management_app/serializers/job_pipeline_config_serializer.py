from typing import Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from apps.auth_totp_mail.models.mail_template_models import MailTemplate
from apps.auth_totp_mail.serializers.mail_template_serializers import (
    MailTemplateReadSerializer,
)
from apps.base.decorators.datetime_format_decorator import datetime_format_decorator
from apps.base.serializers.base_serializer import (
    BaseReadOnlyFieldsSerializer,
    BaseAndAuditSerializer,
    BaseCompanySerializer,
)
from apps.job_management_app.mixins.sequence_mixin import SequenceNumberMixin
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
    JobPipelineConfigStepModel,
    JobPipelineStepStatusConfigModel,
    JobPipelineStepPropertyDefaultConfigModel,
    JobPipelineStatusConfigModel,
)

LOCKED_WHEN_IN_USE = {"steps", "code", "name"}


def _get_catalog_status_by_id(
    company_id: int, status_id: Optional[int]
) -> Optional[JobPipelineStatusConfigModel]:
    """Resolve an existing catalog status by id for the given company."""
    if not status_id:
        return None
    return (
        JobPipelineStatusConfigModel.objects.filter(id=status_id)
        .filter(Q(company_id=company_id) | Q(company__code="DEFAULT", is_public=True))
        .first()
    )


def _ensure_default_within_allowed(
    step: JobPipelineConfigStepModel, *statuses: JobPipelineStatusConfigModel | None
):
    """
    Validate defaults are:
      (a) from the same company as the step's pipeline, and
      (b) among the step's allowed statuses (JobPipelineStepStatusModel).
    """
    company_id = getattr(step.pipeline_config, "company_id", None)
    allowed_ids = set(
        JobPipelineStepStatusConfigModel.objects.filter(step=step).values_list(
            "status_id", flat=True
        )
    )

    def _is_company_or_public_default(status: JobPipelineStatusConfigModel) -> bool:
        if status.company_id == company_id:
            return True
        company = getattr(status, "company", None)
        return (
            getattr(status, "is_public", False)
            and getattr(company, "code", None) == "DEFAULT"
        )

    for s in statuses:
        if not s:
            continue
        if not _is_company_or_public_default(s):
            raise serializers.ValidationError(
                "Default/Success/Failed status must belong to the same company as the step."
            )
        if s.id not in allowed_ids:
            raise serializers.ValidationError(
                "Default/Success/Failed status must be one of the step's configured statuses."
            )


class StepAllowedStatusReadSerializer(serializers.ModelSerializer):
    """
    Expose each allowed status on a step.
    We return the catalog status info; `id` here is the JobStepStatus.id.
    """

    id = serializers.IntegerField(source="status.id", read_only=True)
    name = serializers.CharField(source="status.name", read_only=True)
    color = serializers.CharField(source="status.color", read_only=True)

    class Meta:
        model = JobPipelineStepStatusConfigModel
        fields = ["id", "name", "color"]


class StepAllowedStatusWriteSerializer(serializers.Serializer):
    """
    Strict write: only accept existing catalog status IDs.
    """

    status_id = serializers.IntegerField()

    def validate(self, attrs):
        if not attrs.get("status_id"):
            raise serializers.ValidationError("status_id is required.")
        return attrs


class StepDefaultsReadSerializer(serializers.ModelSerializer):
    default_status = serializers.SerializerMethodField()
    success_status = serializers.SerializerMethodField()
    failed_status = serializers.SerializerMethodField()
    success_mail_template = MailTemplateReadSerializer(
        source="success_mail_template_id", read_only=True
    )
    failed_mail_template = MailTemplateReadSerializer(
        source="failed_mail_template_id", read_only=True
    )

    class Meta:
        model = JobPipelineStepPropertyDefaultConfigModel
        fields = [
            "id",
            "default_status",
            "success_status",
            "failed_status",
            "success_mail_template",
            "failed_mail_template",
            "is_success_auto_send",
            "is_failed_auto_send",
        ]

    @staticmethod
    def _mini_status(s: JobPipelineStatusConfigModel | None):
        if not s:
            return None
        return {"id": s.id, "name": s.name}

    def get_default_status(self, obj):
        return self._mini_status(obj.default_status)

    def get_success_status(self, obj):
        return self._mini_status(obj.success_status)

    def get_failed_status(self, obj):
        return self._mini_status(obj.failed_status)


class StepDefaultsWriteSerializer(serializers.Serializer):
    """
    Strict write: refer to catalog statuses by IDs only.
    If any field is provided, default_id is required.
    """

    default_id = serializers.IntegerField(required=True)
    success_id = serializers.IntegerField(required=True)
    failed_id = serializers.IntegerField(required=True)
    success_mail_template = serializers.PrimaryKeyRelatedField(
        queryset=MailTemplate.objects.all(), required=False, allow_null=True
    )
    failed_mail_template = serializers.PrimaryKeyRelatedField(
        queryset=MailTemplate.objects.all(), required=False, allow_null=True
    )
    is_success_auto_send = serializers.BooleanField(required=False, default=False)
    is_failed_auto_send = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        d, s, f = attrs["default_id"], attrs["success_id"], attrs["failed_id"]
        if len({d, s, f}) != 3:
            raise serializers.ValidationError(
                {"default": "default_id, success_id and failed_id must be different."}
            )
        if attrs.get("is_success_auto_send", False) and not attrs.get(
            "success_mail_template"
        ):
            raise serializers.ValidationError(
                {
                    "success_mail_template": "Mail template is Required when is_success_auto_send."
                }
            )
        if attrs.get("is_failed_auto_send", False) and not attrs.get(
            "failed_mail_template"
        ):
            raise serializers.ValidationError(
                {
                    "failed_mail_template": "Mail template is Required when is_failed_auto_send."
                }
            )
        return attrs


@datetime_format_decorator(fields=["write_date", "create_date"])
class JobPipelineStepReadSerializer(BaseReadOnlyFieldsSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    statuses = StepAllowedStatusReadSerializer(many=True, read_only=True)
    defaults = StepDefaultsReadSerializer(read_only=True)

    class Meta:
        model = JobPipelineConfigStepModel
        fields = [
            "id",
            "name",
            "color",
            "order",
            "is_active",
            "status",
            "status_display",
            "is_default",
            "is_offer",
            "statuses",
            "defaults",
            "write_date",
            "create_date",
        ]


class JobPipelineStepWriteSerializer(BaseAndAuditSerializer):
    """
    - `statuses`: list of { "status_id": <existing JobStepStatus.id> }
    - `defaults`: { "default_id": ..., "success_id": ..., "failed_id": ... }
    """

    inject_company_id = False
    id = serializers.IntegerField(required=False)
    statuses = StepAllowedStatusWriteSerializer(many=True, allow_empty=False)
    defaults = StepDefaultsWriteSerializer(required=True)

    def validate_statuses(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("At least 3 statuses are required.")
        ids = [item["status_id"] for item in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError(
                "Duplicate status_id values are not allowed."
            )
        return value

    class Meta:
        model = JobPipelineConfigStepModel
        fields = [
            "id",
            "name",
            "color",
            "order",
            "is_offer",
            "is_active",
            "status",
            "statuses",
            "defaults",
        ]


@datetime_format_decorator(fields=["write_date", "create_date"])
class JobPipelineConfigReadSerializer(BaseReadOnlyFieldsSerializer):
    steps = JobPipelineStepReadSerializer(many=True, read_only=True)

    class Meta:
        model = JobPipelineConfigModel
        fields = [
            "id",
            "company_id",
            "code",
            "description",
            "name",
            "is_default",
            "is_active",
            "status",
            "steps",
            "write_date",
            "create_date",
            "is_public",
        ]


@datetime_format_decorator(fields=["write_date", "create_date"])
class JobPipelineConfigDetailSerializer(BaseReadOnlyFieldsSerializer):
    steps = JobPipelineStepReadSerializer(many=True, read_only=True)
    is_in_use = serializers.SerializerMethodField()

    class Meta:
        model = JobPipelineConfigModel
        fields = [
            "id",
            "company_id",
            "code",
            "name",
            "description",
            "is_default",
            "is_active",
            "status",
            "is_public",
            "steps",
            "write_date",
            "create_date",
            "is_in_use",
        ]

    def get_is_in_use(self, obj):
        return obj.is_in_use


class JobPipelineConfigWriteSerializer(SequenceNumberMixin, BaseAndAuditSerializer):
    """
    Write contract (strict):
    - steps[].statuses[] requires status_id that exists in JobStepStatus for the same company
    - defaults.* require existing catalog IDs and must be among allowed statuses of the step
    """

    inject_company_id = True
    steps = JobPipelineStepWriteSerializer(many=True, required=False)

    # Allow blank so clients can omit it and get an auto-generated value.
    code = serializers.CharField(required=False, allow_blank=True)

    # SequenceNumberMixin config
    sequence_config = {
        "number_field": "code",
        "prefix": "PIP",
        "separator": "-",
        "padding": 3,
        "scope_fields": ["company_id"],
        "scope_source": "mixed",  # body first, then request.user/token
    }

    class Meta:
        model = JobPipelineConfigModel
        fields = [
            "id",
            "company_id",
            "code",
            "name",
            "description",
            "is_default",
            "is_active",
            "status",
            "steps",
        ]

    def _get_company_id(self) -> int:
        """
        Single source of truth for company_id throughout this serializer.

        Priority: JWT payload → request.user attribute.
        Raises AttributeError/KeyError early if neither is present so the
        caller gets a clear error rather than a silent None.
        """
        request = self.context["request"]
        payload = getattr(request, "auth", None) and request.auth.payload
        if payload and "company_id" in payload:
            return payload["company_id"]
        return request.company_id

    def validate(self, attrs):
        is_default = attrs.get(
            "is_default", getattr(self.instance, "is_default", False)
        )
        company_id = self._get_company_id()
        
        if self.instance is None:
            if "steps" not in self.initial_data or not self.initial_data.get("steps"):
                raise serializers.ValidationError(
                    {"steps": "At least one step is required."}
                )
            if is_default:
                exists = JobPipelineConfigModel.objects.filter(
                    company_id=company_id, is_default=True, is_deleted=False
                ).exists()
                if exists:
                    raise serializers.ValidationError(
                        {"detail": "You already have a default pipeline."}
                    )
            return attrs

        pipeline_in_use = self.context.get("pipeline_in_use", True)
        if pipeline_in_use:
            submitted_locked = LOCKED_WHEN_IN_USE & set(self.initial_data.keys())
            if submitted_locked:
                raise serializers.ValidationError(
                    {"detail": "This pipeline is in use by one or more job posts."}
                )
        if "steps" in self.initial_data and not self.initial_data.get("steps"):
            raise serializers.ValidationError(
                {"steps": "You cannot delete all steps. Include at least one step."}
            )
        if is_default and not self.instance.is_default:
            exists = (
                JobPipelineConfigModel.objects.filter(
                    company_id=company_id, is_default=True, is_deleted=False
                )
                .exclude(id=self.instance.id)
                .exists()
            )
            if exists:
                raise serializers.ValidationError(
                    {"detail": "Another pipeline is already default."}
                )
        return attrs

    def to_representation(self, instance):
        return JobPipelineConfigReadSerializer(instance, context=self.context).data

    # @staticmethod
    # def _validate_default_step(steps):
    #     if not steps:
    #         return
    #     defaults = [s for s in steps if s.get("is_default")]
    #     if len(defaults) != 1:
    #         raise serializers.ValidationError({"steps": "Exactly one step must be marked as default."})

    @staticmethod
    def _validate_unique_orders(steps):
        if any(("order" not in s) or (s.get("order") in (None, "")) for s in steps):
            raise serializers.ValidationError({"steps": "Order is required"})
        orders = [s.get("order") for s in steps if "order" in s]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError(
                {"steps": "Step orders must be unique within a pipeline."}
            )

    @transaction.atomic
    def create(self, validated_data):
        steps_data = validated_data.pop("steps", [])
        self._validate_unique_orders(steps_data)

        pipeline = super().create(validated_data)
        company_id = pipeline.company_id

        for step_payload in steps_data:
            statuses_payload = step_payload.pop("statuses", [])
            defaults_payload = step_payload.pop("defaults", None)

            step = JobPipelineConfigStepModel.objects.create(
                pipeline_config=pipeline,
                **step_payload,
            )
            if statuses_payload:
                link_objs = []
                for s in statuses_payload:
                    st = _get_catalog_status_by_id(company_id, s.get("status_id"))
                    if not st:
                        raise serializers.ValidationError(
                            {"steps": [f"Invalid status_id for step: {step.name}"]}
                        )
                    link_objs.append(
                        JobPipelineStepStatusConfigModel(step=step, status=st)
                    )
                JobPipelineStepStatusConfigModel.objects.bulk_create(
                    link_objs, ignore_conflicts=True
                )

            if defaults_payload:
                d = defaults_payload

                def_ref = _get_catalog_status_by_id(company_id, d.get("default_id"))
                if not def_ref:
                    raise serializers.ValidationError(
                        {"steps": [f"Invalid default_id for step: {step.name}"]}
                    )

                succ_ref = (
                    _get_catalog_status_by_id(company_id, d.get("success_id"))
                    if d.get("success_id")
                    else None
                )
                fail_ref = (
                    _get_catalog_status_by_id(company_id, d.get("failed_id"))
                    if d.get("failed_id")
                    else None
                )

                _ensure_default_within_allowed(step, def_ref, succ_ref, fail_ref)

                defaults_obj = JobPipelineStepPropertyDefaultConfigModel(
                    step=step,
                    default_status=def_ref,
                    success_status=succ_ref,
                    failed_status=fail_ref,
                    success_mail_template_id=d.get("success_mail_template"),
                    failed_mail_template_id=d.get("failed_mail_template"),
                    is_success_auto_send=d.get("is_success_auto_send", False),
                    is_failed_auto_send=d.get("is_failed_auto_send", False),
                )
                defaults_obj.full_clean()
                defaults_obj.save()

        return pipeline

    @transaction.atomic
    def update(self, instance, validated_data):
        steps_data = validated_data.pop("steps", None)
        instance = super().update(instance, validated_data)

        if steps_data is None:
            return instance

        # self._validate_default_step(steps_data)
        self._validate_unique_orders(steps_data)

        existing_steps = {s.id: s for s in instance.steps.all()}
        kept_step_ids = set()

        for step_payload in steps_data:
            step_id = step_payload.get("id")
            statuses_payload = step_payload.pop("statuses", None)
            defaults_payload = step_payload.pop("defaults", None)

            if step_id and step_id in existing_steps:
                step = existing_steps[step_id]
                for k, v in step_payload.items():
                    setattr(step, k, v)
                step.save(
                    update_fields=["name", "color", "order", "is_active", "status"]
                )
            else:
                step = JobPipelineConfigStepModel.objects.create(
                    pipeline_config=instance,
                    **step_payload,
                )

            kept_step_ids.add(step.id)

            if statuses_payload is not None:
                company_id = instance.company_id
                desired_status_ids = set()

                for s in statuses_payload:
                    st = _get_catalog_status_by_id(company_id, s.get("status_id"))
                    if not st:
                        raise serializers.ValidationError(
                            {"steps": [f"Invalid status_id for step: {step.name}"]}
                        )
                    desired_status_ids.add(st.id)

                current_status_ids = set(
                    step.statuses.values_list("status_id", flat=True)
                )

                to_add = desired_status_ids - current_status_ids
                if to_add:
                    JobPipelineStepStatusConfigModel.objects.bulk_create(
                        [
                            JobPipelineStepStatusConfigModel(step=step, status_id=sid)
                            for sid in to_add
                        ],
                        ignore_conflicts=True,
                    )

                to_remove = current_status_ids - desired_status_ids
                if to_remove:
                    step.statuses.filter(status_id__in=to_remove).delete()

            if defaults_payload is not None:
                d = defaults_payload or {}
                company_id = instance.company_id

                def_ref = _get_catalog_status_by_id(company_id, d.get("default_id"))
                succ_ref = _get_catalog_status_by_id(company_id, d.get("success_id"))
                fail_ref = _get_catalog_status_by_id(company_id, d.get("failed_id"))
                if not all((def_ref, succ_ref, fail_ref)):
                    raise serializers.ValidationError(
                        {"steps": [f"Invalid status for step: {step.name}"]}
                    )
                _ensure_default_within_allowed(step, def_ref, succ_ref, fail_ref)
                payload = dict(
                    default_status=def_ref,
                    success_status=succ_ref,
                    failed_status=fail_ref,
                    success_mail_template_id=(d.get("success_mail_template")),
                    failed_mail_template_id=(d.get("failed_mail_template")),
                    is_success_auto_send=bool(d.get("is_success_auto_send", False)),
                    is_failed_auto_send=bool(d.get("is_failed_auto_send", False)),
                )
                defaults_obj = JobPipelineStepPropertyDefaultConfigModel.objects.filter(
                    step=step
                ).first()
                if defaults_obj:
                    for k, v in payload.items():
                        setattr(defaults_obj, k, v)
                else:
                    defaults_obj = JobPipelineStepPropertyDefaultConfigModel(
                        step=step, **payload
                    )
                try:
                    defaults_obj.full_clean()
                except DjangoValidationError as e:
                    raise serializers.ValidationError(
                        {"steps": [f"Defaults invalid for the step: {step.name}"]}
                    )
                defaults_obj.save()

        instance.steps.exclude(id__in=kept_step_ids).delete()
        return instance


class JobPipelineStatusConfigSerializer(BaseAndAuditSerializer):
    inject_company_id = True
    id = serializers.IntegerField(read_only=True)
    company = BaseCompanySerializer(read_only=True)
    name = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    is_public = serializers.BooleanField(read_only=True)

    class Meta:
        model = JobPipelineStatusConfigModel
        fields = [
            "id",
            "company",
            "name",
            "is_active",
            "create_date",
            "description",
            "color",
            "is_public",
        ]

    def validate(self, attrs):
        request = self.context.get("request", None)
        company_id = getattr(request, "company_id", None)
        name = attrs.get("name") or (
            getattr(self.instance, "name", None) if self.instance else None
        )

        if company_id and name:
            qs = JobPipelineStatusConfigModel.objects.filter(
                company_id=company_id, name=name
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"name": "This status name already exists for the company."}
                )
        return attrs


class OperatorJobPipelineStatusConfigSerializer(BaseAndAuditSerializer):
    inject_company_id = True

    id = serializers.IntegerField(read_only=True)
    company = BaseCompanySerializer(read_only=True)
    name = serializers.CharField(required=True, allow_blank=False, trim_whitespace=True)
    is_public = serializers.BooleanField(default=True, required=False, allow_null=True)

    class Meta:
        model = JobPipelineStatusConfigModel
        fields = [
            "id",
            "company",
            "name",
            "is_active",
            "create_date",
            "description",
            "is_public",
        ]

    def validate(self, attrs):
        request = self.context.get("request", None)
        company_id = getattr(request, "company_id", None)
        name = attrs.get("name") or (
            getattr(self.instance, "name", None) if self.instance else None
        )

        if company_id and name:
            qs = JobPipelineStatusConfigModel.objects.filter(
                company_id=company_id, name=name
            )
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"name": "This status name already exists for the company."}
                )
        return attrs


class OperatorJobPipelineConfigWriteSerializer(BaseAndAuditSerializer):
    """
    Write contract (strict):
    - steps[].statuses[] requires status_id that exists in JobStepStatus for the same company
    - defaults.* require existing catalog IDs and must be among allowed statuses of the step
    """

    inject_company_id = True
    steps = JobPipelineStepWriteSerializer(many=True, required=True)
    is_public = serializers.BooleanField(default=True, required=False, allow_null=True)

    class Meta:
        model = JobPipelineConfigModel
        fields = [
            "id",
            "company_id",
            "code",
            "name",
            "description",
            "is_default",
            "is_active",
            "status",
            "steps",
            "is_public",
        ]

    def validate(self, attrs):
        if self.instance is None:
            if "steps" not in self.initial_data or not self.initial_data.get("steps"):
                raise serializers.ValidationError(
                    {"steps": "At least one step is required."}
                )
            return attrs

        if "steps" in self.initial_data and not self.initial_data.get("steps"):
            raise serializers.ValidationError(
                {"steps": "You cannot delete all steps. Include at least one step."}
            )

        return attrs

    def to_representation(self, instance):
        return JobPipelineConfigReadSerializer(instance, context=self.context).data

    @staticmethod
    def _validate_default_step(steps):
        if not steps:
            return
        defaults = [s for s in steps if s.get("is_default")]
        if len(defaults) != 1:
            raise serializers.ValidationError(
                {"steps": "Exactly one step must be marked as default."}
            )

    @staticmethod
    def _validate_unique_orders(steps):
        orders = [s.get("order") for s in steps if "order" in s]
        if len(orders) != len(set(orders)):
            raise serializers.ValidationError(
                {"steps": "Step orders must be unique within a pipeline."}
            )

    @transaction.atomic
    def create(self, validated_data):
        steps_data = validated_data.pop("steps", [])
        self._validate_default_step(steps_data)
        self._validate_unique_orders(steps_data)

        pipeline = super().create(validated_data)

        for step_payload in steps_data:
            statuses_payload = step_payload.pop("statuses", [])
            defaults_payload = step_payload.pop("defaults", None)

            step = JobPipelineConfigStepModel.objects.create(
                pipeline_config=pipeline,
                **step_payload,
            )
            if statuses_payload:
                company_id = pipeline.company_id
                link_objs = []
                for s in statuses_payload:
                    st = _get_catalog_status_by_id(company_id, s.get("status_id"))
                    if not st:
                        raise serializers.ValidationError(
                            {"steps": [f"Invalid status_id for step: {step.name}"]}
                        )
                    link_objs.append(
                        JobPipelineStepStatusConfigModel(step=step, status=st)
                    )
                JobPipelineStepStatusConfigModel.objects.bulk_create(
                    link_objs, ignore_conflicts=True
                )

            if defaults_payload:
                d = defaults_payload
                company_id = pipeline.company_id

                def_ref = _get_catalog_status_by_id(company_id, d.get("default_id"))
                if not def_ref:
                    raise serializers.ValidationError(
                        {"steps": [f"Invalid default_id for step: {step.name}"]}
                    )

                succ_ref = (
                    _get_catalog_status_by_id(company_id, d.get("success_id"))
                    if d.get("success_id")
                    else None
                )
                fail_ref = (
                    _get_catalog_status_by_id(company_id, d.get("failed_id"))
                    if d.get("failed_id")
                    else None
                )

                _ensure_default_within_allowed(step, def_ref, succ_ref, fail_ref)

                defaults_obj = JobPipelineStepPropertyDefaultConfigModel(
                    step=step,
                    default_status=def_ref,
                    success_status=succ_ref,
                    failed_status=fail_ref,
                    success_mail_template_id=d.get("success_mail_template_id"),
                    failed_mail_template_id=d.get("failed_mail_template_id"),
                    is_success_auto_send=d.get("is_success_auto_send", False),
                    is_failed_auto_send=d.get("is_failed_auto_send", False),
                )
                defaults_obj.full_clean()
                defaults_obj.save()

        return pipeline

    @transaction.atomic
    def update(self, instance, validated_data):
        steps_data = validated_data.pop("steps", None)
        instance = super().update(instance, validated_data)

        if steps_data is None:
            return instance

        self._validate_default_step(steps_data)
        self._validate_unique_orders(steps_data)

        existing_steps = {s.id: s for s in instance.steps.all()}
        kept_step_ids = set()

        for step_payload in steps_data:
            step_id = step_payload.get("id")
            statuses_payload = step_payload.pop("statuses", None)
            defaults_payload = step_payload.pop("defaults", None)

            if step_id and step_id in existing_steps:
                step = existing_steps[step_id]
                for k, v in step_payload.items():
                    setattr(step, k, v)
                step.save(
                    update_fields=[
                        "name",
                        "color",
                        "order",
                        "is_active",
                        "status",
                        "is_default",
                    ]
                )
            else:
                step = JobPipelineConfigStepModel.objects.create(
                    pipeline_config=instance,
                    **step_payload,
                )

            kept_step_ids.add(step.id)

            if statuses_payload is not None:
                company_id = instance.company_id
                desired_status_ids = set()

                for s in statuses_payload:
                    st = _get_catalog_status_by_id(company_id, s.get("status_id"))
                    if not st:
                        raise serializers.ValidationError(
                            {"steps": [f"Invalid status_id for step: {step.name}"]}
                        )
                    desired_status_ids.add(st.id)

                current_status_ids = set(
                    step.statuses.values_list("status_id", flat=True)
                )

                to_add = desired_status_ids - current_status_ids
                if to_add:
                    JobPipelineStepStatusConfigModel.objects.bulk_create(
                        [
                            JobPipelineStepStatusConfigModel(step=step, status_id=sid)
                            for sid in to_add
                        ],
                        ignore_conflicts=True,
                    )

                to_remove = current_status_ids - desired_status_ids
                if to_remove:
                    step.statuses.filter(status_id__in=to_remove).delete()

            if defaults_payload is not None:
                d = defaults_payload
                defaults_obj, _ = (
                    JobPipelineStepPropertyDefaultConfigModel.objects.get_or_create(
                        step=step
                    )
                )

                if d:
                    company_id = instance.company_id
                    def_ref = _get_catalog_status_by_id(company_id, d.get("default_id"))
                    if not def_ref:
                        raise serializers.ValidationError(
                            {"steps": [f"Invalid default_id for step: {step.name}"]}
                        )

                    succ_ref = (
                        _get_catalog_status_by_id(company_id, d.get("success_id"))
                        if d.get("success_id")
                        else None
                    )
                    fail_ref = (
                        _get_catalog_status_by_id(company_id, d.get("failed_id"))
                        if d.get("failed_id")
                        else None
                    )

                    _ensure_default_within_allowed(step, def_ref, succ_ref, fail_ref)

                    defaults_obj.default_status = def_ref
                    defaults_obj.success_status = succ_ref
                    defaults_obj.failed_status = fail_ref
                    defaults_obj.success_mail_template_id = d.get(
                        "success_mail_template_id"
                    )
                    defaults_obj.failed_mail_template_id = d.get(
                        "failed_mail_template_id"
                    )
                    defaults_obj.is_success_auto_send = d.get(
                        "is_success_auto_send", False
                    )
                    defaults_obj.is_failed_auto_send = d.get(
                        "is_failed_auto_send", False
                    )
                    defaults_obj.full_clean()
                    defaults_obj.save()

        instance.steps.exclude(id__in=kept_step_ids).delete()
        return instance
