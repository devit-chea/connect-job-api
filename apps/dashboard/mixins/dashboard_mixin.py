from datetime import datetime, time

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.auth_oauth.constants.auth_constants import UserTypes


class DashboardFilterMixin:
    def _access_control_validate(self, user_context):
        user_type = getattr(user_context, "user_type", None)
        company_id = getattr(user_context, "company_id", None)
        user_id = getattr(user_context, "user_id", None)
        user_ucp_id = getattr(user_context, "user_company_profile_id", None)

        supported_user_types = {
            UserTypes.ADMIN_RECRUITER.value,
            UserTypes.RECRUITER.value,
            UserTypes.OPERATOR.value,
        }

        if user_type == UserTypes.APPLICANT.value:
            raise PermissionDenied(
                "Access denied: User type 'applicant' is not permitted to use this filter."
            )

        if user_type is None:
            raise PermissionDenied("Access denied: User type is missing.")

        if user_type not in supported_user_types:
            raise PermissionDenied(f"Unsupported user type: '{user_type}'.")

    def apply_date_filters(self, request, queryset, date_field="post_date"):
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        month = request.query_params.get("month")

        qs = queryset

        if start_date and end_date:
            # Convert start_date
            if isinstance(start_date, str):
                start_date = datetime.fromisoformat(start_date).date()
            elif isinstance(start_date, datetime):
                start_date = start_date.date()

            # Convert end_date
            if isinstance(end_date, str):
                end_date = datetime.fromisoformat(end_date).date()
            elif isinstance(end_date, datetime):
                end_date = end_date.date()

            start_dt = timezone.make_aware(datetime.combine(start_date, time.min))
            end_dt = timezone.make_aware(datetime.combine(end_date, time.max))

            qs = qs.filter(**{f"{date_field}__range": (start_dt, end_dt)})

        if month:
            y, m = month.split("-")
            qs = qs.filter(
                **{
                    f"{date_field}__year": int(y),
                    f"{date_field}__month": int(m),
                }
            )

        return qs

    def apply_role_filter_job(self, request, queryset):
        self._access_control_validate(request)

        if getattr(request, "user_type", "").lower() in (UserTypes.RECRUITER.value,):
            # only jobs created by the recruiter
            queryset = queryset.filter(create_uid=request.user_id)
        # Admin recruiters see all
        return queryset

    def apply_role_filter_applied(self, request, queryset):
        self._access_control_validate(request)

        if getattr(request, "user_type", "").lower() in (UserTypes.RECRUITER.value,):
            # only jobs created by the recruiter
            queryset = queryset.filter(job_post__create_uid=request.user_id)
        # Admin recruiters see all
        return queryset
