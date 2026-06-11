from bs4 import BeautifulSoup
import re

TEMPLATE_VARIABLE_LABELS = {
    "applicant_name": "Applicant Name",
    "job_title": "Job Title",
    "company_name": "Company",
    "location": "Location Name",
    "invited_at": "Invite Date",
    "invitation_type": "Invitation Type",
    "additional_message": "Additional Message",
    "recruiter_name": "Recruiter Name",
    "job_id": "Job ID",
    "job_application": "Job Application",
}


def convert_mention_to_django_template(html: str) -> str:
    """
    Convert mention spans to Django template variables.

    Input:  <span class="mention" data-template="{*Client.FirstName*}">Client.FirstName</span>
    Output: {{ Client.FirstName }}
    """
    soup = BeautifulSoup(html, "html.parser")

    for span in soup.find_all("span", class_="mention"):
        data_template = span.get("data-template", "")
        # Extract value between {* and *}
        match = re.search(r"\{\*(.*?)\*\}", data_template)
        if match:
            variable_name = match.group(1).strip()
            span.replace_with(f"{{{{ {variable_name} }}}}")

    return str(soup)


def convert_django_template_to_mention(html: str) -> str:
    """
    Convert Django template variables back to mention spans with human-readable labels.

    Input:  {{ applicant_name }}
    Output: <span class="mention" data-template="{*applicant_name*}">Applicant Name</span>
    """
    def replace_match(match):
        variable_name = match.group(1).strip()
        label = TEMPLATE_VARIABLE_LABELS.get(variable_name, variable_name)
        return f"<span class='mention' data-template='{{*{variable_name}*}}'>{label}</span>"

    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", replace_match, html)
