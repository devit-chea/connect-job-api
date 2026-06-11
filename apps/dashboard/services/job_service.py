from datetime import timedelta
from datetime import datetime, time
from django.utils import timezone

class DashboardService:
    def get_month_comparison_stats(queryset, time_field="create_date"):
        """
        Calculate this-month vs last-month count comparison with trend.
        """
        today = timezone.localdate()
        tz = timezone.get_current_timezone()
        # This month
        first_day_this_month = today.replace(day=1)

        # Last month
        last_day_last_month = first_day_this_month - timedelta(days=1)
        first_day_last_month = last_day_last_month.replace(day=1)

        # covert dateformat
        this_month_start = timezone.make_aware(
            datetime.combine(first_day_this_month, time.min), tz
        )
        this_month_end = timezone.make_aware(datetime.combine(today, time.max), tz)
        last_month_start = timezone.make_aware(
            datetime.combine(first_day_last_month, time.min), tz
        )
        last_month_end = timezone.make_aware(
            datetime.combine(last_day_last_month, time.max), tz
        )
        # Compute counts
        this_month_count = queryset.filter(
            **{
                f"{time_field}__gte": this_month_start,
                f"{time_field}__lte": this_month_end,
            }
        ).count()

        last_month_count = queryset.filter(
            **{
                f"{time_field}__gte": last_month_start,
                f"{time_field}__lte": last_month_end,
            }
        ).count()

        # Percent calculation
        if last_month_count == 0:
            percent_change = 100.0 if this_month_count > 0 else 0.0
        else:
            percent_change = (
                (this_month_count - last_month_count) / last_month_count
            ) * 100

        # Trend
        if percent_change > 0:
            trend = "up"
        elif percent_change < 0:
            trend = "down"
        else:
            trend = "no_change"

        return {
            "current_month": this_month_count,
            "last_month": last_month_count,
            "percent_change": round(percent_change, 2),
            "trend": trend,
        }
