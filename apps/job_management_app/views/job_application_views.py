from collections import defaultdict

from rest_framework import filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.base.mixins.permission_mixin import PermissionMixin
from apps.base.views.base_views import BaseModelViewSet, BaseListAPIView
from apps.job_management_app.models.job_application_model import JobApplicationModel
from apps.job_management_app.models.job_application_status_history import (
    JobApplicationStatusHistoryModel,
)
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineConfigStepModel,
)
from apps.job_management_app.serializers.job_application_serializer import (
    JobApplicationListResponseSerializer,
    JobApplicationRequestSerializer,
    RecruiterJobApplicationDetailResponseSerializer,
    ApplicantJobApplicationDetailResponseSerializer,
    RecruiterJobApplicationListResponseSerializer,
    JobApplicationEmploymentStatusSerializer
)
from apps.job_management_app.serializers.job_application_status_timeline_history_serializer import (
    ApplicationStatusItemSerializer,
)
from apps.auth_totp_mail.models.invitation_models import Invitation
from apps.job_management_app.services.job_application_services import JobApplicationServices


class JobApplicationView(BaseModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = JobApplicationRequestSerializer
    queryset = JobApplicationModel.objects.all().order_by("-id")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "apply_message",
        "email",
        "applicant_name",
        "apply_date",
        "job_post__title",
        "job_post__time_type",
        "job_post__remote_type",
    ]
    ordering_fields = ["id"]

    def get_queryset(self):
        user_id = self.request.user.id
        user_company_profile_id = getattr(self.request, 'user_company_profile_id', None)
        queryset = super().get_queryset()

        if not user_id or not user_company_profile_id:
            return JobApplicationModel.objects.none()

        queryset = queryset.filter(
            create_uid=user_id, 
            create_ucp_id=user_company_profile_id
        )

        return self.filter_queryset(queryset)

    def get_serializer_class(self):
        action_serializer_map = {
            "update": JobApplicationRequestSerializer,
            "partial_update": JobApplicationRequestSerializer,
            "retrieve": ApplicantJobApplicationDetailResponseSerializer,
            "list": JobApplicationListResponseSerializer,
        }
        return action_serializer_map.get(self.action, self.serializer_class)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="application-statuses",
    )
    @action(detail=True, methods=["get"], url_path="application-statuses")
    def application_statuses(self, request, pk=None):
        app = self.get_object()
        pipeline_cfg = app.pipeline_config
        if not pipeline_cfg:
            return Response([])
        steps = list(
            JobPipelineConfigStepModel.objects.filter(
                pipeline_config=pipeline_cfg, is_active=True
            )
            .select_related(
                "defaults__default_status",
                "defaults__success_status",
                "defaults__failed_status",
            )
            .order_by("order")
        )
        if not steps:
            return Response([])
        first_step = steps[0]
        step_ids = [step.id for step in steps]
        history = list(
            JobApplicationStatusHistoryModel.objects.filter(application_id=app.id)
            .select_related("status")
            .order_by("create_date")
        )
        # Fetch ALL invitations for all steps in one query
        all_invitations = list(
            Invitation.objects.filter(
                job_application_id=app.id,
                pipeline_step_id__in=step_ids,
            )
            .select_related("mail_template")
            .order_by("create_date")  # latest first
        )

        # Group all invitations by step_id
        raw_by_step = defaultdict(list)
        for inv in all_invitations:
            raw_by_step[inv.pipeline_step_id].append(inv)

        def collect_subs(root_id, invs):
            subs = []
            children = sorted(
                [inv for inv in invs if inv.rescheduled_from_id == root_id],
                key=lambda x: x.create_date,
                reverse=False,  # oldest first
            )
            for child in children:
                subs.append(child)
                subs.extend(collect_subs(child.id, invs))
            return subs

        # Per step: group originals with their full reschedule chain
        invitations_by_step = {}
        for step_id, invs in raw_by_step.items():
            referenced_ids = {
                inv.rescheduled_from_id
                for inv in invs
                if inv.rescheduled_from_id is not None
            }

            entries = []
            visited_ids = set()

            # Originals = rescheduled_from_id is None AND referenced by others
            originals = [
                inv for inv in invs
                if inv.rescheduled_from_id is None and inv.id in referenced_ids
            ]

            # Standalones = rescheduled_from_id is None AND not referenced by anyone
            standalones = [
                inv for inv in invs
                if inv.rescheduled_from_id is None and inv.id not in referenced_ids
            ]

            for original in originals:
                if original.id in visited_ids:
                    continue
                subs = collect_subs(original.id, invs)
                entries.append({"main": original, "subs": subs})
                visited_ids.add(original.id)
                for sub in subs:
                    visited_ids.add(sub.id)

            for standalone in standalones:
                if standalone.id in visited_ids:
                    continue
                entries.append({"main": standalone, "subs": []})
                visited_ids.add(standalone.id)

            # Sort by main.id ASC
            entries = sorted(entries, key=lambda x: x["main"].id)
            invitations_by_step[step_id] = entries

        actions_by_step = defaultdict(list)
        first_arrival_dt = {}

        for h in history:
            if h.step_id:
                actions_by_step[h.step_id].append(h)
            if h.to_step_id and h.to_step_id not in first_arrival_dt:
                first_arrival_dt[h.to_step_id] = h.create_date
        if first_step.id not in first_arrival_dt:
            first_arrival_dt[first_step.id] = app.apply_date

        cur_order = app.pipeline_step_order or 0
        cur_status_obj = getattr(app, "pipeline_status", None)

        def _is_status(step_status, property_status):
            return (
                getattr(property_status, "id", None) is not None
                and getattr(step_status, "id", None) is not None
                and property_status.id == step_status.id
            )

        items = []
        for step in steps:
            is_current = step.order == cur_order
            reached = step.id in first_arrival_dt
            status_obj = None
            if actions_by_step.get(step.id):
                status_obj = actions_by_step[step.id][-1].status
            if status_obj is None and is_current and cur_status_obj:
                status_obj = cur_status_obj
            if status_obj is None and not reached:
                status_obj = getattr(
                    getattr(step, "defaults", None), "default_status", None
                )
            defaults = getattr(step, "defaults", None)
            default_status = getattr(defaults, "default_status", None)
            success_status = getattr(defaults, "success_status", None)
            failed_status = getattr(defaults, "failed_status", None)

            is_default = _is_status(status_obj, default_status)
            is_success = _is_status(status_obj, success_status)
            is_failed = _is_status(status_obj, failed_status)

            date_val = first_arrival_dt.get(step.id)
            if date_val is None and is_current:
                date_val = app.apply_date

            step_entries = invitations_by_step.get(step.id, [])

            # Latest entry is last (ASC sort by main.id)
            latest_entry = step_entries[-1] if step_entries else None
            latest_invitation_id = (
                latest_entry["main"].id if latest_entry else None
            )
            latest_sub_id = (
                latest_entry["subs"][-1].id   # ← last not first
                if latest_entry and latest_entry["subs"]
                else None
            )

            items.append(
                {
                    "step_id": step.id,
                    "step_name": step.name,
                    "order": step.order,
                    "status": status_obj,
                    "date": date_val,
                    "is_current": is_current,
                    "is_default": is_default,
                    "is_success": is_success,
                    "is_failed": is_failed,
                    "invitations": step_entries,
                    "latest_invitation_id": latest_invitation_id,
                    "latest_sub_id": latest_sub_id,
                }
            )

        return Response(ApplicationStatusItemSerializer(items, many=True).data)


class RecruiterJobApplicationView(PermissionMixin, BaseModelViewSet):
    permission_codename = ["recruiter_applicant", "admin_recruiter_applicant"]
    serializer_class = JobApplicationRequestSerializer
    queryset = JobApplicationModel.objects.all().order_by("-id")
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "apply_message",
        "applicant_name",
        "applicant_current_position",
        "email",
        "phone_number",
        "pipeline_status_name",
        "job_post__title",
    ]
    ordering_fields = ["id"]

    def get_queryset(self):
        company_id = getattr(self.request, "company_id", None)
        user_type = getattr(self.request, "user_type", None)
        company_profile_id = getattr(self.request, "user_company_profile_id", None)
        qs = (
            super()
            .get_queryset()
            .select_related("job_post", "pipeline_step", "pipeline_status")
            .filter(is_deleted=False)
        )

        if not company_id:
            return qs.none()
        qs = qs.filter(job_post__company_id=company_id)

        # For Admin Recruiter -> allow "applicant_view" or "all" applicants
        if user_type == "admin_recruiter":
            applicant_view = self.request.query_params.get("applicant_view", "all")
            specific_ucp_id = self.request.query_params.get("ucp_id")

            if specific_ucp_id:  # Filter by specific user_company_profile_id
                return qs.filter(job_post__create_ucp_id=specific_ucp_id)
            if applicant_view == "my":
                if not company_profile_id:
                    return qs.none()
                qs = qs.filter(JobApplicationServices.recruiter_scope_query(company_profile_id)).distinct()

            return qs

        # For normal recruiter -> own + assign_jobs
        if not company_profile_id:
            return qs.none()

        return qs.filter(JobApplicationServices.recruiter_scope_query(company_profile_id)).distinct()

    def get_serializer_class(self):
        if self.action == "update_employment_status":
            return JobApplicationEmploymentStatusSerializer
        action_serializer_map = {
            "retrieve": RecruiterJobApplicationDetailResponseSerializer,
            "list": RecruiterJobApplicationListResponseSerializer,
        }
        return action_serializer_map.get(self.action, self.serializer_class)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update_employment_status(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = JobApplicationEmploymentStatusSerializer(
            instance, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {"message": "Employment status updated successfully."},
            status=status.HTTP_200_OK,
        )


class RecruiterJobListApplicantsView(PermissionMixin, BaseListAPIView):
    queryset = JobApplicationModel.objects.all()
    serializer_class = JobApplicationListResponseSerializer
    filter_backends = []
    permission_codename = ["recruiter_applicant", "admin_recruiter_applicant"]
    search_fields = ["applicant_name", "email", "phone_number"]

    def list(self, request, *args, **kwargs):
        job_post_id = kwargs.get("job_post_id", None)
        queryset = JobApplicationModel.objects.filter(job_post_id=job_post_id)
        queryset = self.filter_queryset(queryset)

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
