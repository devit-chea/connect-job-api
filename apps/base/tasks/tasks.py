from config.celery import app
from apps.base.tasks_celery.send_email import send_email as task_send_email


@app.task
def send_email(title, body, from_email, to_email, company_id):
    task_send_email(title, body, from_email, to_email, company_id, body)
