from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.base.models.sys_value_model import SysValueCategories, SysValue

DATA = {
    "employment_type": [
        "Full-Time",
        "Part-Time",
        "Contract",
        "Internship",
        "Freelance",
        "Temporary",
        "Other",
    ],
    "position_title": [
        "Software Engineer",
        "Data Analyst",
        "Project Manager",
        "UI/UX Designer",
        "DevOps Engineer",
        "HR Manager",
        "Python API developer",
        "Frontend Developer",
        "Backend Developer",
        "Full Stack Developer",
        "Mobile App Developer",
        "Data Scientist",
        "Machine Learning Engineer",
        "Product Manager",
        "Business Analyst",
        "Marketing Manager",
        "Sales Executive",
        "Account Manager",
        "Customer Support Specialist",
        "Technical Support Engineer",
        "Systems Administrator",
        "Network Engineer",
        "Cybersecurity Analyst",
        "Quality Assurance Engineer",
        "Test Automation Engineer",
        "Content Writer",
        "Copywriter",
        "Event Coordinator",
        "Graphic Designer",
        "Video Editor",
        "Animator",
        "SEO Specialist",
        "Social Media Manager",
        "Finance Manager",
        "Teacher",
        "Recruitment Specialist",
        "Accountant",
        "Operations Manager",
        "Logistics Coordinator",
        "Supply Chain Analyst",
        "Research Scientist",
        "Electrical Engineer",
        "Chemical Engineer",
        "Biomedical Engineer",
        "Translator",
        "Mechanical Engineer",
        "Pharmacist",
        "Nurse Practitioner",
        "Medical Laboratory Technician",
        "Veterinarian",
        "College Lecturer",
        "Interpreter",
        "Other",
    ],
    "company_size": [
        {"name": "1-10 Employees", "range": "[1,10)"},
        {"name": "11-50 Employees", "range": "[11,50)"},
        {"name": "51-200 Employees", "range": "[51,200)"},
        {"name": "201-1000 Employees", "range": "[201,1000)"},
        {"name": "1001-5000 Employees", "range": "[1001,5000)"},
        {"name": "5001-10000 Employees", "range": "[5001,10000)"},
    ],
    "industry": [
        "Information Technology",
        "Healthcare",
        "Finance and Banking",
        "Transportation and Logistics",
        "Education",
        "Real Estate and Construction",
        "Hospitality and Tourism",
        "Telecommunications",
        "Media and Entertainment",
        "Environmental Services",
        "Other",
    ],
    "job_level": [
        "Apprentice",
        "Associate Professional",
        "Professional",
        "Associate Management",
        "Middle Management",
        "Senior Management",
        "Executive",
    ],
    "skill": [
        # Software / IT
        "Python",
        "Java",
        "JavaScript",
        "TypeScript",
        "Django",
        "Spring Boot",
        "Node.js",
        "REST API Design",
        "GraphQL",
        "Microservices",
        "SQL",
        "NoSQL",
        "Git",
        "Docker",
        "Kubernetes",
        "CI/CD",
        "Cloud Computing",
        "AWS",
        "Azure",
        "Linux",
        "System Design",
        "Cybersecurity Fundamentals",
        "Network Administration",
        "DevOps Practices",
        # Data / AI
        "Data Analysis",
        "Data Visualization",
        "Power BI",
        "Tableau",
        "Machine Learning",
        "Deep Learning",
        "Statistical Analysis",
        "ETL Pipelines",
        "Big Data Processing",
        "Data Modeling",
        # Design / Creative
        "UI Design",
        "UX Research",
        "Wireframing",
        "Prototyping",
        "Figma",
        "Adobe Photoshop",
        "Adobe Illustrator",
        "Video Editing",
        "Motion Graphics",
        "Graphic Design",
        "Content Creation",
        # Product / Project / Business
        "Project Management",
        "Agile Methodology",
        "Scrum",
        "Product Management",
        "Roadmap Planning",
        "Stakeholder Management",
        "Business Analysis",
        "Process Improvement",
        "Market Research",
        # Marketing / Sales
        "Digital Marketing",
        "SEO",
        "SEM",
        "Social Media Marketing",
        "Content Marketing",
        "Email Marketing",
        "Sales Strategy",
        "CRM Management",
        "Lead Generation",
        "Negotiation",
        # Operations / Finance / HR
        "Financial Analysis",
        "Accounting",
        "Budgeting",
        "Payroll Management",
        "Human Resource Management",
        "Recruitment",
        "Performance Management",
        "Supply Chain Management",
        "Logistics Planning",
        "Operations Management",
        # Healthcare / Science
        "Clinical Research",
        "Laboratory Techniques",
        "Medical Documentation",
        "Patient Care",
        "Pharmaceutical Knowledge",
        "Quality Control",
        "Regulatory Compliance",
        # Education / Language
        "Teaching",
        "Curriculum Development",
        "Training & Development",
        "Public Speaking",
        "Technical Writing",
        "Translation",
        "Interpretation",
        # Soft Skills (important!)
        "Communication",
        "Problem Solving",
        "Critical Thinking",
        "Teamwork",
        "Leadership",
        "Time Management",
        "Adaptability",
        "Attention to Detail",
    ],
    "work_arrangement": [
        "On-site",
        "Remote",
        "Hybrid",
    ],
}


class Command(BaseCommand):
    help = "Seed sys_values. Use --sync to deactivate removed values instead of skipping them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sync",
            action="store_true",
            help=(
                "Sync mode: adds new values and soft-deletes (active=False) any existing "
                "values no longer in DATA. Safe for production — never hard-deletes rows."
            ),
        )
        parser.add_argument(
            "--category",
            type=str,
            default=None,
            help="Only sync a specific category by name (e.g. --category job_level).",
        )

    def handle(self, *args, **kwargs):
        sync_mode = kwargs["sync"]
        target_category = kwargs["category"]

        if target_category and target_category not in DATA:
            self.stdout.write(self.style.ERROR(f"Category '{target_category}' not found in DATA."))
            return

        categories_to_process = (
            {target_category: DATA[target_category]} if target_category else DATA
        )

        try:
            with transaction.atomic():
                for category_name, values in categories_to_process.items():
                    self.stdout.write(f"\n{category_name}")
                    category = self._resolve_category(category_name)
                    self._sync_values(category, category_name, values, sync_mode)

                self.stdout.write(self.style.SUCCESS("\nAll sys_value seeding completed!"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}"))

    def _resolve_category(self, category_name):
        """Get or create the category, merging duplicates into the oldest one."""
        now = timezone.now()
        categories = SysValueCategories.objects.filter(name=category_name).order_by("id")

        if not categories.exists():
            category = SysValueCategories.objects.create(name=category_name)
            self.stdout.write(self.style.SUCCESS(f"  Created category"))
            return category

        category = categories.first()
        duplicates = list(categories[1:])

        if duplicates:
            duplicate_ids = [d.pk for d in duplicates]
            moved = SysValue.objects.filter(category_id__in=duplicate_ids).update(
                category_id=category.pk, write_date=now
            )
            SysValueCategories.objects.filter(pk__in=duplicate_ids).delete()
            self.stdout.write(self.style.WARNING(
                f"  Merged {moved} value(s) and deleted {len(duplicate_ids)} duplicate category/categories"
            ))
        else:
            self.stdout.write(self.style.WARNING(f"  Category already exists"))

        return category

    def _sync_values(self, category, category_name, values, sync_mode):
        """Add new values, deduplicate, re-activate, and optionally deactivate stale ones."""
        now = timezone.now()
        canonical = self._parse_canonical(values)

        existing_map = self._load_existing(category.pk)

        self._deactivate_duplicates(existing_map, category_name, now)
        self._add_new_values(existing_map, canonical, category.pk, category_name, now)

        if sync_mode:
            self._deactivate_stale(existing_map, canonical, category_name, now)

    def _parse_canonical(self, values):
        """Parse DATA values into {name: {index, range_value}}."""
        result = {}
        for index, item in enumerate(values):
            if isinstance(item, dict):
                result[item["name"]] = {"index": index, "range_value": item.get("range")}
            else:
                result[item] = {"index": index, "range_value": None}
        return result

    def _load_existing(self, category_id):
        """Load all SysValue rows for a category, grouped by name."""
        existing_map = defaultdict(list)
        for sv in SysValue.objects.filter(category_id=category_id):
            existing_map[sv.name].append(sv)
        return existing_map

    def _deactivate_duplicates(self, existing_map, category_name, now):
        """Deactivate duplicate rows with the same name, keeping the oldest (lowest pk)."""
        for name, svs in existing_map.items():
            if len(svs) > 1:
                svs_sorted = sorted(svs, key=lambda sv: sv.pk)
                duplicate_pks = [sv.pk for sv in svs_sorted[1:]]
                SysValue.objects.filter(pk__in=duplicate_pks).update(active=False, write_date=now)
                self.stdout.write(self.style.WARNING(
                    f"  Deactivated {len(duplicate_pks)} duplicate(s) for '{name}': pks={duplicate_pks}"
                ))

    def _add_new_values(self, existing_map, canonical, category_id, category_name, now):
        """Insert missing values and re-activate any that were previously deactivated."""
        new_items = []

        for name, meta in canonical.items():
            if name in existing_map:
                # Re-activate any inactive rows for this name
                for sv in existing_map[name]:
                    if not sv.active:
                        sv.active = True
                        sv.write_date = now
                        sv.save(update_fields=["active", "write_date"])
                        self.stdout.write(self.style.SUCCESS(f"  Re-activated '{name}'"))
                continue

            new_items.append(SysValue(
                create_date=now,
                write_date=now,
                name=name,
                code=None,
                description="",
                order_index=meta["index"],
                default=True,
                active=True,
                properties=None,
                object_id=None,
                is_other=False,
                company_id=None,
                content_type_id=None,
                category_id=category_id,
                range_value=meta["range_value"],
                create_ucp_id=None,
                write_ucp_id=None,
            ))

        if new_items:
            SysValue.objects.bulk_create(new_items)
            self.stdout.write(self.style.SUCCESS(f"  Seeded {len(new_items)} new value(s)"))
        else:
            self.stdout.write(self.style.WARNING(f"  No new values to add"))

    def _deactivate_stale(self, existing_map, canonical, category_name, now):
        """Deactivate values that exist in DB but are no longer in DATA."""
        stale_pks = [
            sv.pk
            for name, svs in existing_map.items()
            if name not in canonical
            for sv in svs
            if sv.active
        ]
        stale_names = [name for name in existing_map if name not in canonical]

        if stale_pks:
            SysValue.objects.filter(pk__in=stale_pks).update(active=False, write_date=now)
            self.stdout.write(self.style.WARNING(
                f"  Deactivated {len(stale_pks)} stale value(s): {stale_names}"
            ))