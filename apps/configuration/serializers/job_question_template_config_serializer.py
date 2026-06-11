from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import serializers

from apps.base.serializers.base_serializer import BaseAndAuditSerializer
from apps.configuration.models.job_question_template_config_model import (
    JobQuestionConfigModel,
    JobQuestionTemplateConfigModel,
    QuestionTypes,
)


class JobQuestionConfigWriteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    choices = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        required=False,
    )
    question_title = serializers.CharField(required=True)
    question_type = serializers.CharField(required=True)

    class Meta:
        model = JobQuestionConfigModel
        fields = [
            "id",
            "question_title",
            "question_type",
            "choices",
            "is_required",
            "order",
        ]

    def validate(self, attrs):
        question_type = attrs.get("question_type")
        choices = attrs.get("choices", [])

        if question_type in [
            QuestionTypes.SINGLE_CHOICE,
            QuestionTypes.MULTIPLE_CHOICE,
        ]:
            if not choices:
                raise serializers.ValidationError(
                    {"choices": f"Choices cannot be empty."}
                )

            if len(choices) < 2:
                raise serializers.ValidationError(
                    {"choices": f"Choices must contain at least 2 items."}
                )

        elif question_type == QuestionTypes.TEXT and choices:
            raise serializers.ValidationError(
                {"choices": f"Choices are not allowed for this question type."}
            )

        return attrs


class JobQuestionConfigReadSerializer(serializers.ModelSerializer):
    question_type_display = serializers.CharField(
        source="get_question_type_display", read_only=True
    )

    class Meta:
        model = JobQuestionConfigModel
        fields = [
            "id",
            "question_title",
            "question_type",
            "question_type_display",
            "choices",
            "is_required",
            "order",
        ]


class JobQuestionTemplateConfigWriteSerializer(BaseAndAuditSerializer):
    questions = JobQuestionConfigWriteSerializer(
        many=True, required=True, allow_null=False
    )

    class Meta:
        model = JobQuestionTemplateConfigModel
        fields = [
            "id",
            "template_name",
            "description",
            "is_active",
            "status",
            "questions",
        ]

    def validate_questions(self, value):
        if not value:  # catches [] or None
            raise ValidationError("At least one question is required.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        questions_data = validated_data.pop("questions", [])
        template = super().create(validated_data)
        # This code not insert Company_id
        # template = JobQuestionTemplateConfigModel.objects.create(**validated_data)

        if questions_data:
            question_objs = [
                JobQuestionConfigModel(question_template=template, **q)
                for q in questions_data
            ]
            JobQuestionConfigModel.objects.bulk_create(question_objs)

        return template

    @transaction.atomic
    def update(self, instance, validated_data):
        questions_data = validated_data.pop("questions", None)

        # Update template fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if questions_data is not None:
            self._sync_questions(instance, questions_data)

        return instance

    @staticmethod
    def _sync_questions(template_instance, questions_data):
        """
        Handles nested question update:
        - Validate IDs
        - Soft-delete removed questions
        - Update existing questions
        - Create new questions
        """
        sent_ids = [q.get("id") for q in questions_data if q.get("id")]
        new_questions_data = [q for q in questions_data if not q.get("id")]

        # Fetch existing questions in bulk
        existing_qs = template_instance.questions.filter(id__in=sent_ids)
        existing_dict = {q.id: q for q in existing_qs}

        # Validate IDs
        if sent_ids and len(existing_qs) != len(sent_ids):
            invalid_ids = [qid for qid in sent_ids if qid not in existing_dict]
            raise serializers.ValidationError(
                f"These question ids do not exist in this template: {invalid_ids}"
            )

        # Soft-delete removed questions
        template_instance.questions.exclude(id__in=sent_ids).delete()

        # Update existing
        for q_data in questions_data:
            q_id = q_data.get("id")
            if q_id:
                question = existing_dict[q_id]
                for attr, value in q_data.items():
                    if attr != "id":
                        setattr(question, attr, value)
                question.save()

        # Create new
        for q_data in new_questions_data:
            q_data["choices"] = q_data.get("choices") or []
            template_instance.questions.create(**q_data)


class OperatorJobQuestionTemplateConfigWriteSerializer(BaseAndAuditSerializer):
    questions = JobQuestionConfigWriteSerializer(
        many=True, required=True, allow_null=False
    )
    is_public = serializers.BooleanField(default=True, required=False, allow_null=True)

    class Meta:
        model = JobQuestionTemplateConfigModel
        fields = [
            "id",
            "template_name",
            "description",
            "is_active",
            "status",
            "questions",
            "is_public",
        ]

    def validate_questions(self, value):
        if not value:  # catches [] or None
            raise ValidationError("At least one question is required.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        questions_data = validated_data.pop("questions", [])
        template = super().create(validated_data)
        # This code not insert Company_id
        # template = JobQuestionTemplateConfigModel.objects.create(**validated_data)

        if questions_data:
            question_objs = [
                JobQuestionConfigModel(question_template=template, **q)
                for q in questions_data
            ]
            JobQuestionConfigModel.objects.bulk_create(question_objs)

        return template

    @transaction.atomic
    def update(self, instance, validated_data):
        questions_data = validated_data.pop("questions", None)

        # Update template fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if questions_data is not None:
            self._sync_questions(instance, questions_data)

        return instance

    @staticmethod
    def _sync_questions(template_instance, questions_data):
        """
        Handles nested question update:
        - Validate IDs
        - Soft-delete removed questions
        - Update existing questions
        - Create new questions
        """
        sent_ids = [q.get("id") for q in questions_data if q.get("id")]
        new_questions_data = [q for q in questions_data if not q.get("id")]

        # Fetch existing questions in bulk
        existing_qs = template_instance.questions.filter(id__in=sent_ids)
        existing_dict = {q.id: q for q in existing_qs}

        # Validate IDs
        if sent_ids and len(existing_qs) != len(sent_ids):
            invalid_ids = [qid for qid in sent_ids if qid not in existing_dict]
            raise serializers.ValidationError(
                f"These question ids do not exist in this template: {invalid_ids}"
            )

        # Soft-delete removed questions
        template_instance.questions.exclude(id__in=sent_ids).delete()

        # Update existing
        for q_data in questions_data:
            q_id = q_data.get("id")
            if q_id:
                question = existing_dict[q_id]
                for attr, value in q_data.items():
                    if attr != "id":
                        setattr(question, attr, value)
                question.save()

        # Create new
        for q_data in new_questions_data:
            q_data["choices"] = q_data.get("choices") or []
            template_instance.questions.create(**q_data)


class JobQuestionTemplateConfigListSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    question_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = JobQuestionTemplateConfigModel
        fields = [
            "id",
            "template_name",
            "description",
            "is_active",
            "status",
            "status_display",
            "question_count",
        ]


class JobQuestionTemplateConfigDetailSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    questions = JobQuestionConfigReadSerializer(many=True, read_only=True)

    class Meta:
        model = JobQuestionTemplateConfigModel
        fields = [
            "id",
            "template_name",
            "description",
            "is_active",
            "status",
            "status_display",
            "questions",
        ]
