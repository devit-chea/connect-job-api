from datetime import datetime
from django.db.models import Sum
from django.utils.dateparse import parse_date

def parse_month(month_str):
    # expects YYYY-MM
    if not month_str:
        return None, None
    y, m = month_str.split("-")
    return int(y), int(m)
