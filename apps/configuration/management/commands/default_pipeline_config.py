from __future__ import annotations

from typing import Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.auth_totp_mail.models.mail_template_models import MailTemplate
from apps.base.models.company_model import Company
from apps.job_management_app.models.job_pipeline_config_model import (
    JobPipelineStatusConfigModel,
    JobPipelineConfigModel,
    JobPipelineConfigStepModel,
    JobPipelineStepStatusConfigModel,
    JobPipelineStepPropertyDefaultConfigModel,
)

SUCCESS_SUBJECT = "You passed to the next stage - {{ job.title }} at {{ company_name }}"
FAILED_SUBJECT = "Application outcome - {{ job.title }} at {{ company_name }}"

SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>You passed to the next stage - {{ job.title }} at {{ company_name }}</title>
</head>
<body style="margin:0;background:#f6f6f6;">
<div style="max-width:640px;margin:0 auto;padding:24px;">
<div style="background:#ffffff;border:1px solid #e5e5e5;border-radius:8px;padding:20px;">
<h2 style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:18px;color:#111111;">

        Update on your application
</h2>
<p style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;color:#111111;">

        Dear {{ candidate_name }}, We're pleased to inform you that you've successfully passed to the next stage of our recruitment process for the {{ job.title }} position at {{ company_name }}. Further details will be shared with you shortly.
</p>
<hr style="border:0;border-top:1px solid #eeeeee;margin:16px 0;">
<p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#111111;">

        Best regards,<br>

        {{ recruiter_name|default:"Your Name" }} - Recruitment Team - {{ company_name }}
</p>
</div>
</div>
</body>
</html>"""

FAILED_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Application outcome - {{ job.title }} at {{ company_name }}</title>
</head>
<body style="margin:0;background:#f6f6f6;">
<div style="max-width:640px;margin:0 auto;padding:24px;">
<div style="background:#ffffff;border:1px solid #e5e5e5;border-radius:8px;padding:20px;">
<h2 style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:18px;color:#111111;">

        Update on your application
</h2>
<p style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;color:#111111;">

        Dear {{ candidate_name }}, We appreciate your application for the {{ job.title }} role. Unfortunately, you have not been selected to move forward in the process.
</p>
<p style="margin:0 0 12px 0;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;color:#111111;">

        We wish you the best in your future career.
</p>
<hr style="border:0;border-top:1px solid #eeeeee;margin:16px 0;">
<p style="margin:0;font-family:Arial,Helvetica,sans-serif;font-size:16px;color:#111111;">

        Best regards,<br>

        {{ recruiter_name|default:"Your Name" }} - Recruitment Team - {{ company_name }}
</p>
</div>
</div>
</body>
</html>"""

STATUS_GROUPS: Dict[str, List[Dict[str, str]]] = {
    "APPLY": [
        {"name": "New", "description": "Default status", "color": "#60A5FA"},
        {"name": "Completed", "description": "Can move to the next step", "color": "#34D399"},
        {"name": "Withdrawn", "description": "The candidate voluntarily cancels their application.",
         "color": "#9CA3AF"},
    ],
    "SCREENING": [
        {"name": "Under Review", "description": "Default status", "color": "#FCD34D"},
        {"name": "Qualified", "description": "Qualified at screening. Ready for next step.", "color": "#10B981"},
        {"name": "Unqualified", "description": "Does not meet screening criteria.", "color": "#EF4444"},
    ],
    "INTERVIEW": [
        {"name": "Scheduled", "description": "Interview scheduled. Default status", "color": "#60A5FA"},
        {"name": "Completed", "description": "Interview completed. Ready for next step.", "color": "#34D399"},
        {"name": "No-show", "description": "Candidate did not attend a scheduled interview.", "color": "#9CA3AF"},
        {"name": "Failed", "description": "Did not pass interview.", "color": "#EF4444"},
    ],
    "FUNCTIONAL_TEST": [
        {"name": "Sent", "description": "Default status", "color": "#60A5FA"},
        {"name": "Submitted", "description": "Candidate submitted the test.", "color": "#F59E0B"},
        {"name": "Passed", "description": "Passed functional test. Ready for next step.", "color": "#10B981"},
        {"name": "Failed", "description": "Failed functional test.", "color": "#EF4444"},
    ],
    "OFFER": [
        {"name": "Offer pending", "description": "Default status", "color": "#60A5FA"},
        {"name": "Passed", "description": "Process to onboard, Auto sent email", "color": "#10B981"},
        {"name": "Rejected", "description": "End, Auto sent email", "color": "#EF4444"},
    ],
}

STEP_SPECS = [
    {"code": "APPLY", "name": "Apply", "order": 1, "color": "#60A5FA"},
    {"code": "SCREENING", "name": "Screening", "order": 2, "color": "#6EE7B7"},
    {"code": "INTERVIEW", "name": "Interview", "order": 3, "color": "#FCD34D"},
    {"code": "FUNCTIONAL_TEST", "name": "Functional Testing", "order": 4, "color": "#C4B5FD"},
    {"code": "OFFER", "name": "Offer", "order": 5, "color": "#34D399"},
]

DEFAULT_MAPPING = {
    "APPLY": {"default": "New", "success": "Completed", "failed": "Withdrawn"},
    "SCREENING": {"default": "Under Review", "success": "Qualified", "failed": "Unqualified"},
    "INTERVIEW": {"default": "Scheduled", "success": "Completed", "failed": "Failed"},
    "FUNCTIONAL_TEST": {"default": "Sent", "success": "Passed", "failed": "Failed"},
    "OFFER": {"default": "Offer pending", "success": "Passed", "failed": "Rejected"},
}

AUTO_SEND = {
    "APPLY": {"success": False, "failed": False},
    "SCREENING": {"success": False, "failed": False},
    "INTERVIEW": {"success": False, "failed": False},
    "FUNCTIONAL_TEST": {"success": False, "failed": False},
    "OFFER": {"success": True, "failed": True},
}

SUCCESS_TEMPLATE_TYPE = "pipeline.success"
FAILED_TEMPLATE_TYPE = "pipeline.failed"


def _sync_step_status_links(step: JobPipelineConfigStepModel, status_names_in_order: List[str]) -> None:
    current = {
        link.status.name: link
        for link in (
            JobPipelineStepStatusConfigModel.objects
            .select_related("status")
            .filter(step=step)
        )
    }
    for name in status_names_in_order:
        lookup = {"name": name, "company": step.pipeline_config.company}
        status = JobPipelineStatusConfigModel.objects.get(**lookup)

        if name not in current:
            JobPipelineStepStatusConfigModel.objects.create(step=step, status=status)
    to_keep = set(status_names_in_order)
    for name, link in current.items():
        if name not in to_keep:
            link.delete()


def _upsert_step(
        *,
        pipeline: JobPipelineConfigModel,
        name: str,
        color: str,
        order: int,
        is_active: bool,
        status: str,
        is_default: bool,
) -> JobPipelineConfigStepModel:
    obj = JobPipelineConfigStepModel.objects.filter(pipeline_config=pipeline, name=name).first()
    if obj:
        changed = False
        for f, v in {
            "color": color,
            "order": order,
            "is_active": is_active,
            "status": status,
            "is_default": is_default,
        }.items():
            if hasattr(obj, f) and getattr(obj, f) != v:
                setattr(obj, f, v)
                changed = True
        if changed:
            obj.save()
        return obj

    return JobPipelineConfigStepModel.objects.create(
        pipeline_config=pipeline,
        name=name,
        color=color,
        order=order,
        is_active=is_active,
        status=status,
        is_default=is_default,
    )


def _get_or_create_template(
        specific_type: str,
        title: str,
        subject: str,
        body: str,
        company: Company,
) -> Optional[MailTemplate]:
    """If MailTemplate has 'company', use DEFAULT company; else global."""
    base_qs = MailTemplate.objects.filter(specific_type=specific_type, company=company)
    mt = base_qs.order_by("id").first()
    if mt:
        return mt

    try:
        create_kwargs = {"specific_type": specific_type, "title": title, "subject": subject, "body": body,
                         "company": company}
        return MailTemplate.objects.create(**create_kwargs)
    except Exception:
        return base_qs.order_by("id").first()

def _sync_template(
        specific_type: str,
        title: str,
        subject: str,
        body: str,
        company: Company,
) -> Optional[MailTemplate]:
    existing = MailTemplate.objects.filter(specific_type=specific_type, company=company)
    print(f"[_sync_template] {specific_type} — found {existing.count()} existing rows: "
          f"{list(existing.values('id', 'specific_type', 'subject'))}")

    mt, created = MailTemplate.objects.update_or_create(
        specific_type=specific_type,
        company=company,
        defaults={
            "title": title,
            "subject": subject,
            "body": body,
        },
    )
    print(f"[_sync_template] {'CREATED' if created else 'UPDATED'} id={mt.id} subject={mt.subject[:60]}")
    return mt

def _apply_defaults(
        step: JobPipelineConfigStepModel,
        *,
        default_status: JobPipelineStatusConfigModel,
        success_status: Optional[JobPipelineStatusConfigModel],
        failed_status: Optional[JobPipelineStatusConfigModel],
        success_mail_template: Optional[MailTemplate],
        failed_mail_template: Optional[MailTemplate],
        is_success_auto_send: bool,
        is_failed_auto_send: bool,
) -> None:
    """
    Persist defaults.
    Fields on the model:
      - default_status, success_status, failed_status (FKs)
      - success_mail_template_id, failed_mail_template_id (FKs)
    """
    JobPipelineStepPropertyDefaultConfigModel.objects.update_or_create(
        step=step,
        defaults={
            "default_status": default_status,
            "success_status": success_status,
            "failed_status": failed_status,
            "success_mail_template_id": success_mail_template,
            "failed_mail_template_id": failed_mail_template,
            "is_success_auto_send": is_success_auto_send,
            "is_failed_auto_send": is_failed_auto_send,
        },
    )


def _s(name: str, company: Company) -> JobPipelineStatusConfigModel:
    lookup = {"name": name, "company": company}
    return JobPipelineStatusConfigModel.objects.get(**lookup)


class Command(BaseCommand):
    help = "Seed the default pipeline, resolving company by Company.code='DEFAULT'. Idempotent."

    def add_arguments(self, parser):
        parser.add_argument("--code", type=str, required=True, help="Pipeline code (unique upsert key).")
        parser.add_argument("--name", type=str, default="Engineering Hiring")
        parser.add_argument("--description", type=str, default="Default pipeline for engineering roles")
        parser.add_argument("--status", type=str, default="ACTIVE")
        parser.add_argument("--is-active", action="store_true", help="Set pipeline is_active=True")
        parser.add_argument("--is-default", action="store_true", help="Set pipeline is_default=True")
        parser.add_argument(
            "--force-only-default",
            action="store_true",
            help="Unset other default pipelines for this company and set this one default.",
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        code = opts["code"]
        name = opts["name"]
        description = opts["description"]
        status = opts["status"]
        is_active = True if not opts.get("is_active") else bool(opts.get("is_active"))
        is_default = bool(opts.get("is_default", False))
        force_only_default = bool(opts.get("force_only_default", False))

        # Resolve company by code="DEFAULT"
        company = Company.objects.filter(code="DEFAULT").first()
        if not company:
            raise CommandError("Company with code='DEFAULT' not found. Please create it first.")

        # Ensure mail templates exist
        mt_success = _sync_template(
            SUCCESS_TEMPLATE_TYPE,
            title="Auto: Passed",
            subject=SUCCESS_SUBJECT,
            body=SUCCESS_HTML,
            company=company,
        )
        mt_failed = _sync_template(
            FAILED_TEMPLATE_TYPE,
            title="Auto: Rejected",
            subject=FAILED_SUBJECT,
            body=FAILED_HTML,
            company=company,
        )
        for group in STATUS_GROUPS.values():
            for s in group:
                get_kwargs = {"name": s["name"], "company": company}
                defaults = {
                    "is_active": True,
                    "description": s.get("description", s["name"])[:500],
                    "color": s.get("color", None),
                    "is_public": True
                }
                obj, _ = JobPipelineStatusConfigModel.objects.get_or_create(
                    **get_kwargs,
                    defaults=defaults,
                )

                changed = False
                wanted_desc = s.get("description", obj.description)
                if obj.description != wanted_desc:
                    obj.description = wanted_desc
                    changed = True
                if not obj.is_active:
                    obj.is_active = True
                    changed = True
                wanted_color = s.get("color", None)
                if getattr(obj, "color", None) != wanted_color:
                    obj.color = wanted_color
                    changed = True
                if changed:
                    obj.save()

        # Upsert pipeline (DEFAULT company)
        pipeline = JobPipelineConfigModel.objects.filter(code=code, company=company).first()
        if pipeline:
            changed = False
            for f, v in {
                "name": name,
                "description": description,
                "status": status,
                "is_active": is_active,
                "is_default": is_default,
            }.items():
                if hasattr(pipeline, f) and getattr(pipeline, f) != v:
                    setattr(pipeline, f, v)
                    changed = True
            if changed:
                pipeline.save()
        else:
            payload = {
                "company": company,
                "code": code,
                "name": name,
                "description": description,
                "status": status,
                "is_active": is_active,
                "is_default": is_default,
                "is_public": True
            }
            pipeline = JobPipelineConfigModel.objects.create(**payload)

        # only-one-default if asked
        if force_only_default and hasattr(JobPipelineConfigModel, "is_default"):
            (JobPipelineConfigModel.objects
             .filter(company=company, is_default=True)
             .exclude(pk=pipeline.pk)
             .update(is_default=False))
            if not pipeline.is_default:
                pipeline.is_default = True
                pipeline.save()

        # Upsert steps -> link statuses -> set defaults + auto-mail
        for spec in STEP_SPECS:
            step = _upsert_step(
                pipeline=pipeline,
                name=spec["name"],
                color=spec["color"],
                order=spec["order"],
                is_active=True,
                status="ACTIVE",
                is_default=(spec["code"] == "APPLY"),
            )

            # Link statuses in declared order
            linked_names = [s["name"] for s in STATUS_GROUPS[spec["code"]]]
            _sync_step_status_links(step, linked_names)

            company = step.pipeline_config.company
            names = DEFAULT_MAPPING[spec["code"]]
            default_obj = _s(names["default"], company)
            success_obj = _s(names["success"], company)
            failed_obj = _s(names["failed"], company)

            auto = AUTO_SEND[spec["code"]]

            _apply_defaults(
                step,
                default_status=default_obj,
                success_status=success_obj,
                failed_status=failed_obj,
                success_mail_template=mt_success,
                failed_mail_template=mt_failed,
                is_success_auto_send=bool(auto["success"]),
                is_failed_auto_send=bool(auto["failed"]),
            )

        self.stdout.write(self.style.SUCCESS(
            f"[{company.code}] Pipeline '{pipeline.name}' (code={pipeline.code}, id={pipeline.id}) initialized/updated."
        ))
