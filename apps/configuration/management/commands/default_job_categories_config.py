from django.core.management.base import BaseCommand
from django.db import transaction

from apps.job_management_app.models.job_category_model import JobCategoryModel

JOB_CATEGORY_DATA = [
    {
        "code": "",
        "name": "Business & Management",
        "description": "",
    },
    {
        "code": "",
        "name": "Information Technology (IT)",
        "description": "",
    },
    {
        "code": "",
        "name": "Engineering & Technical",
        "description": "",
    },
    {
        "code": "",
        "name": "Education & Training",
        "description": "",
    },
    {
        "code": "",
        "name": "Sales & Marketing",
        "description": "",
    },
    {
        "code": "",
        "name": "Customer Service & Support",
        "description": "",
    },
    {
        "code": "",
        "name": "Finance & Accounting",
        "description": "",
    },
    {
        "code": "",
        "name": "Legal & Compliance",
        "description": "",
    },
    {
        "code": "",
        "name": "Healthcare & Medical",
        "description": "",
    },
    {
        "code": "",
        "name": "Design, Media & Creative",
        "description": "",
    },
    {
        "code": "",
        "name": "Manufacturing & Operations",
        "description": "",
    },
    {
        "code": "",
        "name": "Transportation & Logistics",
        "description": "",
    },
    {
        "code": "",
        "name": "Hospitality, Tourism & Food",
        "description": "",
    },
    {
        "code": "",
        "name": "Retail & Consumer Services",
        "description": "",
    },
    {
        "code": "",
        "name": "Construction & Skilled Trades",
        "description": "",
    },
    {
        "code": "",
        "name": "Telecommunications",
        "description": "",
    },
    {
        "code": "",
        "name": "Human Resources",
        "description": "",
    },
    {
        "code": "",
        "name": "Science & Research",
        "description": "",
    }
]


class Command(BaseCommand):
    help = "Seed default job categories into JobCategoryModel"

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for item in JOB_CATEGORY_DATA:
            name = item["name"]
            defaults = {
                "code": item.get("code", ""),
                "description": item.get("description", ""),
            }

            _, created = JobCategoryModel.objects.update_or_create(
                name=name,
                defaults=defaults,
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Job categories seeded. created={created_count}, updated={updated_count}"
            )
        )
