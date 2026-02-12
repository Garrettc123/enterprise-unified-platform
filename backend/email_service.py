"""Email notification service for sending SMTP-based email notifications."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

# Email templates for different notification types
EMAIL_TEMPLATES = {
    "task_assigned": {
        "subject": "Task Assigned: {task_title}",
        "html": (
            "<h2>You have been assigned a new task</h2>"
            "<p><strong>Task:</strong> {task_title}</p>"
            "<p><strong>Project:</strong> {project_name}</p>"
            "<p><strong>Priority:</strong> {priority}</p>"
            "<p><strong>Assigned by:</strong> {assigned_by}</p>"
            "<p>{description}</p>"
        ),
        "text": (
            "You have been assigned a new task\n\n"
            "Task: {task_title}\n"
            "Project: {project_name}\n"
            "Priority: {priority}\n"
            "Assigned by: {assigned_by}\n\n"
            "{description}"
        ),
    },
    "task_updated": {
        "subject": "Task Updated: {task_title}",
        "html": (
            "<h2>A task has been updated</h2>"
            "<p><strong>Task:</strong> {task_title}</p>"
            "<p><strong>Updated by:</strong> {updated_by}</p>"
            "<p><strong>Changes:</strong> {changes}</p>"
        ),
        "text": (
            "A task has been updated\n\n"
            "Task: {task_title}\n"
            "Updated by: {updated_by}\n"
            "Changes: {changes}"
        ),
    },
    "comment_added": {
        "subject": "New Comment on: {task_title}",
        "html": (
            "<h2>New comment on a task</h2>"
            "<p><strong>Task:</strong> {task_title}</p>"
            "<p><strong>Comment by:</strong> {comment_by}</p>"
            "<p>{comment_text}</p>"
        ),
        "text": (
            "New comment on a task\n\n"
            "Task: {task_title}\n"
            "Comment by: {comment_by}\n\n"
            "{comment_text}"
        ),
    },
    "project_invitation": {
        "subject": "You've been invited to project: {project_name}",
        "html": (
            "<h2>Project Invitation</h2>"
            "<p>You have been invited to join the project "
            "<strong>{project_name}</strong>.</p>"
            "<p><strong>Invited by:</strong> {invited_by}</p>"
            "<p><strong>Role:</strong> {role}</p>"
        ),
        "text": (
            "Project Invitation\n\n"
            "You have been invited to join the project {project_name}.\n"
            "Invited by: {invited_by}\n"
            "Role: {role}"
        ),
    },
    "general": {
        "subject": "{subject}",
        "html": "<h2>{subject}</h2><p>{body}</p>",
        "text": "{subject}\n\n{body}",
    },
}


class EmailService:
    """Service for sending email notifications via SMTP."""

    def __init__(
        self,
        smtp_host: str = settings.SMTP_HOST,
        smtp_port: int = settings.SMTP_PORT,
        smtp_username: str = settings.SMTP_USERNAME,
        smtp_password: str = settings.SMTP_PASSWORD,
        use_tls: bool = settings.SMTP_USE_TLS,
        from_address: str = settings.EMAIL_FROM_ADDRESS,
        from_name: str = settings.EMAIL_FROM_NAME,
        enabled: bool = settings.EMAIL_ENABLED,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.use_tls = use_tls
        self.from_address = from_address
        self.from_name = from_name
        self.enabled = enabled

    def _build_message(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> MIMEMultipart:
        """Build a MIME email message."""
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.from_name} <{self.from_address}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        if text_body:
            msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        return msg

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """Send an email via SMTP.

        Args:
            to_email: Recipient email address.
            subject: Email subject line.
            html_body: HTML content of the email.
            text_body: Optional plain text fallback.

        Returns:
            True if email was sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.info("Email sending is disabled. Would send to %s: %s", to_email, subject)
            return False

        msg = self._build_message(to_email, subject, html_body, text_body)

        try:
            if self.use_tls:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls()
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(self.from_address, to_email, msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    server.sendmail(self.from_address, to_email, msg.as_string())

            logger.info("Email sent successfully to %s: %s", to_email, subject)
            return True
        except Exception:
            logger.exception("Failed to send email to %s", to_email)
            return False

    def send_notification(
        self,
        to_email: str,
        notification_type: str,
        context: dict,
    ) -> bool:
        """Send a templated notification email.

        Args:
            to_email: Recipient email address.
            notification_type: Type of notification (e.g. 'task_assigned').
            context: Dictionary of template variables.

        Returns:
            True if email was sent successfully, False otherwise.
        """
        template = EMAIL_TEMPLATES.get(notification_type)
        if not template:
            logger.warning("Unknown notification type: %s, falling back to general", notification_type)
            template = EMAIL_TEMPLATES["general"]

        subject = template["subject"].format_map(context)
        html_body = template["html"].format_map(context)
        text_body = template["text"].format_map(context)

        return self.send_email(to_email, subject, html_body, text_body)

    def get_supported_notification_types(self) -> list:
        """Return list of supported notification types."""
        return list(EMAIL_TEMPLATES.keys())


# Module-level singleton
email_service = EmailService()
