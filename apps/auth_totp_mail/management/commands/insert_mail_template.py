from django.core.management.base import BaseCommand
from apps.auth_totp_mail.models.mail_template_models import MailTemplate


class Command(BaseCommand):
    help = "Insert or update default 'Auto: Job Applied' mail template"

    def handle(self, *args, **options):
        specific_type = "application.submit"

        # 1. Look for duplicates
        templates = MailTemplate.objects.filter(specific_type=specific_type)

        if templates.count() > 1:
            self.stdout.write(self.style.WARNING(f"Found {templates.count()} duplicates for '{specific_type}'. Cleaning up..."))
            # Keep the first one, delete the rest
            first_template = templates.first()
            MailTemplate.objects.filter(specific_type=specific_type).exclude(id=first_template.id).delete()

        # 2. Now update_or_create will run perfectly without crashing
        _, created = MailTemplate.objects.update_or_create(
            specific_type=specific_type,
            defaults={
                "title": "Auto: Job Applied",
                "mail_from": "",
                "subject": "Your Application to {{ job_title }} via {{ company_name }}",
                "body": """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Application Submitted - {{ job_title }} at {{ company_name }}</title>
</head>

<body style="font-family: Arial, Helvetica, sans-serif; font-size: 15px; color: #333; line-height: 1.6; margin: 0; padding: 20px;">

<p>Dear <strong>{{ applicant_name }}</strong>,</p><br>

<p>We’re pleased to inform you that your application, along with your attached documents, for the position of <strong>{{ job_title }}</strong> at <strong>{{ company_name }}</strong> has been successfully submitted.</p><br>

<p><strong>What happens next:</strong></p>

<ul>
    <li><strong>{{ company_name }}</strong> will review your application.</li>
    <li>If your profile matches their requirements, they may contact you directly for interviews or further steps.</li>
</ul>

<br>
<p>We wish you the best of luck in your application journey.</p><br>

<p>Thanks for using Connect Job!</p>
<p><strong>The Connect Job Team</strong></p>

</body>
</html>
""",
            },
        )

        if created:
            self.stdout.write(self.style.SUCCESS("Mail template created successfully."))
        else:
            self.stdout.write(self.style.SUCCESS("Mail template updated successfully."))