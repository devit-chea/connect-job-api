import json
import logging

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.auth_oauth.utils.auth_util import get_active_profile_id
from apps.auth_totp_mail.services.auto_send_mail_service import (
    AutoSendMailService,
    ApplicationSubmitService,
)
from apps.base.decorators.tracking_fields_decorator import inject_tracking_fields
from apps.base.utils.sequence_utils import generate_sequence_number
from apps.job_management_app.constants.job_application_types import EmploymentStatus
from apps.job_management_app.models.job_application_model import (
    JobApplicationQuestionAnswerModel,
    JobApplicationModel,
)
from apps.job_management_app.models.job_application_status_history import (
    JobApplicationStatusHistoryModel,
)
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigModel,
    JobPipelineConfigStepModel,
    JobPipelineStepPropertyDefaultConfigModel,
    JobPipelineStatusConfigModel,
)
from apps.job_management_app.models.job_post_model import JobPostModel
from apps.job_management_app.models.job_question_model import JobPostQuestionModel
from rest_framework import serializers
from django.db.models import Q

logger = logging.getLogger(__name__)


class JobApplicationServices:

    @staticmethod
    def recruiter_scope_query(ucp_id) -> Q:
        """Returns applications belonging to jobs owned or assigned to this recruiter."""
        return Q(job_post__create_ucp_id=ucp_id) | Q(
            job_post__job_post_assigned_recruiters__assigned_ucp_id=ucp_id,
            job_post__job_post_assigned_recruiters__is_deleted=False,
        )

    @staticmethod
    def recruiter_scope_for_invitation_query(ucp_id) -> Q:
        """Returns a filter for invitations belonging to jobs owned or assigned to this recruiter."""
        return (
            Q(job_application__job_post__create_ucp_id=ucp_id)
            | Q(
                job_application__job_post__job_post_assigned_recruiters__assigned_ucp_id=ucp_id,
                job_application__job_post__job_post_assigned_recruiters__is_deleted=False,
            )
        )
    @staticmethod
    def ensure_json_object(val):
        if isinstance(val, dict):
            return val
        if not val:
            return {}
        if isinstance(val, str):
            try:
                v = json.loads(val)
                return v if isinstance(v, dict) else {}
            except Exception:
                return {}
        return {}

    @staticmethod
    def pick_pipeline_config_for_job(job_post):
        pipeline_config = getattr(job_post, "job_pipeline_config", None)
        company_id = getattr(job_post, "company_id", None)
        if pipeline_config and getattr(pipeline_config, "is_active", True):
            return pipeline_config
        pipeline_config = (
            (
                JobPipelineConfigModel.objects.filter(
                    company_id=company_id, is_default=True, is_active=True
                ).first()
            )
            if company_id
            else None
        )
        if pipeline_config:
            return pipeline_config
        raise serializers.ValidationError(
            {"detail": "Unable to apply for this job at the moment."}
        )

    @staticmethod
    def pick_initial_step_status(config: JobPipelineConfigModel):
        """
        Step: job_pipeline_config_step where is_default=True (fallback: lowest order)
        Status: job_pipeline_step_property_default.default_status_id for that step
                (fallback: None or any sensible default from your catalog)
        """
        if not config:
            return None, None

        step = (
            JobPipelineConfigStepModel.objects.filter(
                pipeline_config=config, is_active=True, is_deleted=False
            )
            .order_by("order")
            .first()
        )
        if not step:
            return None, None

        step_property = JobPipelineStepPropertyDefaultConfigModel.objects.filter(
            step=step
        ).first()
        status = None
        if step_property and step_property.default_status_id:
            status = JobPipelineStatusConfigModel.objects.filter(
                pk=step_property.default_status_id, is_active=True
            ).first()
        return step, status

    @staticmethod
    @inject_tracking_fields
    def apply_to_job(request, job_post_id, validated_data):
        if not request.user.is_authenticated:
            raise ValidationError("Anonymous users are not allowed.")
        with transaction.atomic():
            job_post = get_object_or_404(
                JobPostModel.objects.select_related("job_pipeline_config"), id=job_post_id
            )

            pipeline_conf = JobApplicationServices.pick_pipeline_config_for_job(job_post)
            step, status = JobApplicationServices.pick_initial_step_status(pipeline_conf)
            profile_id, _ = get_active_profile_id(request)
            code = generate_sequence_number(
                model_class=JobApplicationModel,
                number_field="code",
                scope_filters={"job_post__company_id": job_post.company_id},
                prefix="APP",
            )
            application = JobApplicationModel.objects.create(
                job_post=job_post,
                code=code,
                apply_message=validated_data.get("apply_message", ""),
                cv_file_id=validated_data.get("cv_file_id"),
                cover_letter_file_id=validated_data.get("cover_letter_file_id"),
                additional_file_ids=validated_data.get("additional_file_ids"),
                phone_number=validated_data.get("phone_number"),
                email=validated_data.get("email"),
                meta_data=validated_data.get("meta_data"),
                applicant_name=validated_data.get("applicant_name"),
                applicant_current_position=validated_data.get("current_position"),
                create_uid=validated_data.get("create_uid"),
                write_uid=validated_data.get("write_uid"),
                create_ucp_id=validated_data.get("create_ucp_id"),
                write_ucp_id=validated_data.get("write_ucp_id"),
                pipeline_config=pipeline_conf,
                pipeline_step=step,
                pipeline_status=status,
                pipeline_step_order=getattr(step, "order", 0) if step else 0,
                pipeline_step_name=getattr(step, "name", "") or "",
                pipeline_status_name=getattr(status, "name", "") or "",
                profile_id=profile_id,
                employment_status=EmploymentStatus.ACTIVE.value,
                expected_salary=validated_data.get("expected_salary"),
            )

            answers = validated_data.get("answers", [])
            answer_objs = []
            for ans in answers:
                question = get_object_or_404(JobPostQuestionModel, id=ans["question_id"])
                answer_objs.append(
                    JobApplicationQuestionAnswerModel(
                        application=application,
                        question=question,
                        answer=ans.get("answer", ""),
                    )
                )
            JobApplicationQuestionAnswerModel.objects.bulk_create(answer_objs)

        try:
            ApplicationSubmitService.send_confirmation(application)
        except Exception as e:
            logger.exception(f"Error: {e}")
            
        return application

    @staticmethod
    @transaction.atomic
    def update_pipeline(
        *,
        job_post_id: int,
        application_id: int,
        status: JobPipelineStatusConfigModel,
        actor,
        actor_profile_id,
    ) -> JobApplicationModel:
        """
        Updates pipeline step/status for a given application (under a job_post),
        writes snapshots, triggers auto-email (if status changes), and appends a
        timeline event into application.meta_data["pipeline_events"].
        """
        app = JobApplicationModel.objects.select_related(
            "pipeline_config", "pipeline_step", "pipeline_status", "job_post"
        ).get(pk=application_id, job_post_id=job_post_id, is_deleted=False)
        history_step = app.pipeline_step

        prev_step_id = getattr(app.pipeline_step, "id", None)
        prev_status_id = getattr(app.pipeline_status, "id", None)
        new_step = None
        new_status = status
        request_status = status
        """
        Auto Move to the next step if it is the success status
        in the step.
        """
        candidate_step = new_step or app.pipeline_step
        candidate_status = new_status or app.pipeline_status

        auto_step = False
        auto_from_step_id = getattr(candidate_step, "id", None)
        auto_from_status_id = getattr(app.pipeline_status, "id", None)

        if candidate_step and candidate_status:
            step_props = (
                JobPipelineStepPropertyDefaultConfigModel.objects.only(
                    "success_status_id"
                )
                .filter(step=candidate_step)
                .first()
            )
            if step_props and step_props.success_status_id == candidate_status.id:
                next_step = (
                    JobPipelineConfigStepModel.objects.filter(
                        pipeline_config=app.pipeline_config,
                        is_active=True,
                        order__gt=candidate_step.order,
                    )
                    .order_by("order")
                    .first()
                )
                if next_step:
                    new_step = next_step
                    next_defaults = (
                        JobPipelineStepPropertyDefaultConfigModel.objects.only(
                            "default_status_id"
                        )
                        .filter(step=next_step)
                        .first()
                    )
                    new_status = None
                    if next_defaults and next_defaults.default_status_id:
                        new_status = JobPipelineStatusConfigModel.objects.filter(
                            id=next_defaults.default_status_id, is_active=True
                        ).first()
                    auto_step = True
        # Persist changes (step first, then status) + snapshots
        update_fields = []
        if new_step:
            app.pipeline_step = new_step
            app.pipeline_step_order = getattr(new_step, "order", 0) or 0
            app.pipeline_step_name = new_step.name or ""
            update_fields += [
                "pipeline_step",
                "pipeline_step_order",
                "pipeline_step_name",
            ]

        if new_status:
            app.pipeline_status = new_status
            app.pipeline_status_order = 0
            app.pipeline_status_name = new_status.name or ""
            update_fields += [
                "pipeline_status",
                "pipeline_status_order",
                "pipeline_status_name",
            ]

        app.write_uid = getattr(actor, "id", None)
        update_fields.append("write_uid")
        app.save(update_fields=update_fields)
        # Auto-send (only when status changed)
        if new_status:
            auto_send = AutoSendMailService.trigger_for_status(
                app, request_status, history_step, actor_profile_id
            )
            logging.info(auto_send)
        meta = JobApplicationServices.ensure_json_object(app.meta_data)
        events = meta.get("pipeline_events") or []
        events.append(
            {
                "ts": timezone.now().isoformat(),
                "actor_id": getattr(actor, "id", None),
                "action": "auto_next_step" if auto_step else "change_status",
                "from_step_id": prev_step_id if not auto_step else auto_from_step_id,
                "to_step_id": getattr(app.pipeline_step, "id", None),
                "from_status_id": (
                    prev_status_id if not auto_step else auto_from_status_id
                ),
                "to_status_id": getattr(app.pipeline_status, "id", None),
            }
        )
        meta["pipeline_events"] = events
        app.meta_data = meta
        app.save(update_fields=["meta_data"])

        try:
            JobApplicationStatusHistoryModel.objects.create(
                application=app,
                step=history_step,
                status=status,
                from_step=history_step,
                to_step=app.pipeline_step,
                moved_to_next=bool(new_step),
                is_auto=auto_step,
                to_status=app.pipeline_status,
                create_ucp_id=getattr(actor, "default_user_profile_company", None),
            )
        except Exception as e:
            logging.warning(
                f"[PipelineHistory] failed to write history: {e}", exc_info=True
            )

        return app

    @staticmethod
    def update_job_application_score_by_pk(
        application_pk: int, new_score: float
    ) -> bool:
        """
        Updates the 'score' field for a specific JobApplicationModel instance
        identified by its primary key (pk).

        Args:
            application_pk (int): The primary key (ID) of the JobApplicationModel instance.
            new_score (float): The new score value to set.

        Returns:
            bool: True if the record was successfully updated, False otherwise.

        Raises:
            ObjectDoesNotExist: If no JobApplicationModel with the given pk is found.
        """

        # Use the provided model class name
        model_class = JobApplicationModel

        # We use a transaction to ensure atomicity, although update() is usually atomic.
        with transaction.atomic():
            # Query the database for the specific application instance
            queryset = model_class.objects.filter(pk=application_pk)

            # Check if the object exists before attempting the update
            if not queryset.exists():
                # Raise an exception if the record is not found
                raise ObjectDoesNotExist(
                    f"JobApplicationModel with pk={application_pk} not found."
                )

            # Perform the atomic update on the queryset
            updated_count = queryset.update(score=new_score)

            # updated_count will be 1 if the update was successful, 0 otherwise.
            return updated_count == 1
