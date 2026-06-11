from datetime import timedelta
from django.utils.timezone import now
from django.core.exceptions import PermissionDenied


class DashboardStatsService:
    """
    Generic service for calculating dashboard metrics across multiple models
    (e.g., JobPostModel, JobApplicationModel), with configurable field mappings.
    """

    def __init__(
        self,
        model,
        status_field="status",
        status_map=None,
        filter_map=None,
        date_field=None,
    ):
        """
        :param model: Django model class
        :param status_field: Field name that represents status
        :param status_map: Dict mapping logical statuses to actual model values
        :param filter_map: Dict mapping logical keys -> model field names
               Example:
                   {
                       "company": "company_id",
                       "create_uid": "create_uid",
                       "create_ucp_id": "create_ucp_id",
                   }
        """
        self.model = model
        self.status_field = status_field
        self.status_map = status_map or {}
        self.filter_map = filter_map or {}
        self.date_field = date_field

    def _apply_access_control_filter(self, user_context):
        """
        Apply access control filtering dynamically based on `filter_map`.
        """
        user_type = getattr(user_context, "user_type", None)
        company_id = getattr(user_context, "company_id", None)
        user_id = getattr(user_context, "user_id", None)
        user_ucp_id = getattr(user_context, "user_company_profile_id", None)

        supported_user_types = {
            "super_admin",
            "admin_recruiter",
            "recruiter_admin",
            "recruiter",
        }
        if user_type == "applicant":
            raise PermissionDenied(
                "Access denied: User type 'applicant' is not permitted to use this filter."
            )

        if user_type is None:
            raise PermissionDenied(
                "Access denied: User type is missing (None) and is required for access control."
            )

        if user_type not in supported_user_types:
            raise PermissionDenied(
                f"Unsupported user type for access control: '{user_type}'."
            )

        queryset = self.model.objects.all()

        if user_type == "super_admin" or not user_id:
            return queryset

        filters = {}

        # Recruiter Admin → filter by company
        if user_type == "recruiter_admin" or "admin_recruiter" and company_id:
            company_field = self.filter_map.get("company")
            if company_field:
                filters[company_field] = company_id

        # Recruiter → filter by creator and company
        elif user_type == "recruiter" and company_id and user_id and user_ucp_id:
            company_field = self.filter_map.get("company")
            create_uid_field = self.filter_map.get("create_uid")
            create_ucp_field = self.filter_map.get("create_ucp_id")

            if company_field:
                filters[company_field] = company_id
            if create_uid_field:
                filters[create_uid_field] = user_id
            if create_ucp_field:
                filters[create_ucp_field] = user_ucp_id

        return queryset.filter(**filters)

    def get_stats(self, user_context, dynamic_filters=None, trend=False):
        queryset = self._apply_access_control_filter(user_context)

        if dynamic_filters:
            queryset = queryset.filter(**dynamic_filters)

        total_count = queryset.count()
        results = {"total": total_count}

        # Status-based counts
        if self.status_map:
            for label, value in self.status_map.items():
                results[label] = queryset.filter(**{self.status_field: value}).count()

        # -------------------------
        # Month-over-month comparison (%)
        # -------------------------
        if trend:
            # Field for time-based filtering
            time_field = getattr(self, "date_field", "created_at")

            today = now().date()
            first_day_this_month = today.replace(day=1)
            last_day_last_month = first_day_this_month - timedelta(days=1)
            first_day_last_month = last_day_last_month.replace(day=1)

            this_month_count = queryset.filter(
                **{
                    f"{time_field}__gte": first_day_this_month,
                    f"{time_field}__lte": today,
                }
            ).count()

            last_month_count = queryset.filter(
                **{
                    f"{time_field}__gte": first_day_last_month,
                    f"{time_field}__lte": last_day_last_month,
                }
            ).count()

            if last_month_count == 0:
                percent_change = 100.0 if this_month_count > 0 else 0.0
            else:
                percent_change = (
                    (this_month_count - last_month_count) / last_month_count
                ) * 100

            if percent_change > 0:
                trend = "up"
            elif percent_change < 0:
                trend = "down"
            else:
                trend = "no_change"

            results["month_comparison"] = {
                "current_month": this_month_count,
                "last_month": last_month_count,
                "percent_change": round(percent_change, 2),
                "trend": trend,
            }

        return results
