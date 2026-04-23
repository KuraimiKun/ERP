"""
ERP Services - Notification Service

Provides notification management for the ERP system.
"""

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.core.mail import send_mail
from django.template import Template, Context
from django.conf import settings
from ..models import Notification, EmailTemplate


class NotificationService:
    """Service for managing notifications."""

    @staticmethod
    def create_notification(
        recipient,
        title,
        message,
        notification_type=Notification.NotificationType.INFO,
        related_object=None,
        action_url="",
        send_email=False,
        company=None,
    ):
        """
        Create a notification for a user.

        Args:
            recipient: User to notify
            title: Notification title
            message: Notification message
            notification_type: Type of notification
            related_object: Optional related model instance
            action_url: URL for the notification action
            send_email: Whether to also send an email
            company: Company for email template lookup

        Returns:
            Notification: The created notification
        """
        content_type = None
        object_id = None

        if related_object:
            content_type = ContentType.objects.get_for_model(related_object)
            object_id = related_object.pk

        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            content_type=content_type,
            object_id=object_id,
            action_url=action_url,
        )

        if send_email:
            NotificationService.send_notification_email(notification, company)

        return notification

    @staticmethod
    def send_notification_email(notification, company=None):
        """
        Send email for a notification.

        Args:
            notification: The notification to send email for
            company: Optional company for template lookup
        """
        try:
            # Try to get email template
            template = None
            if company:
                try:
                    template = EmailTemplate.objects.get(company=company, code="notification", is_active=True)
                except EmailTemplate.DoesNotExist:
                    pass

            if template:
                # Use template
                subject = Template(template.subject).render(
                    Context({"notification": notification, "user": notification.recipient})
                )
                html_message = Template(template.body_html).render(
                    Context({"notification": notification, "user": notification.recipient})
                )
                plain_message = (
                    Template(template.body_text).render(
                        Context({"notification": notification, "user": notification.recipient})
                    )
                    if template.body_text
                    else ""
                )
            else:
                # Default template
                subject = notification.title
                html_message = f"""
                <html>
                <body>
                    <h2>{notification.title}</h2>
                    <p>{notification.message}</p>
                    {f'<p><a href="{notification.action_url}">View Details</a></p>' if notification.action_url else ""}
                </body>
                </html>
                """
                plain_message = notification.message

            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.recipient.email],
                html_message=html_message,
                fail_silently=True,
            )

            notification.email_sent = True
            notification.email_sent_at = timezone.now()
            notification.save(update_fields=["email_sent", "email_sent_at"])

        except Exception as e:
            # Log error but don't raise
            print(f"Error sending notification email: {e}")

    @staticmethod
    def mark_as_read(notification):
        """Mark a notification as read."""
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at"])

    @staticmethod
    def mark_all_as_read(user):
        """Mark all notifications for a user as read."""
        Notification.objects.filter(recipient=user, is_read=False).update(is_read=True, read_at=timezone.now())

    @staticmethod
    def get_unread_count(user):
        """Get unread notification count for a user."""
        return Notification.objects.filter(recipient=user, is_read=False).count()

    @staticmethod
    def get_recent_notifications(user, limit=10, include_read=True):
        """
        Get recent notifications for a user.

        Args:
            user: The user to get notifications for
            limit: Maximum number to return
            include_read: Whether to include read notifications

        Returns:
            QuerySet: Recent notifications
        """
        queryset = Notification.objects.filter(recipient=user)
        if not include_read:
            queryset = queryset.filter(is_read=False)
        return queryset.order_by("-created_at")[:limit]

    @staticmethod
    def delete_old_notifications(days=90):
        """
        Delete notifications older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            int: Number of deleted notifications
        """
        threshold = timezone.now() - timezone.timedelta(days=days)
        deleted, _ = Notification.objects.filter(created_at__lt=threshold, is_read=True).delete()
        return deleted


# Convenience functions for common notification types
def notify_task_assigned(task, assigned_by):
    """Notify user of task assignment."""
    if not task.assigned_to or not task.assigned_to.user:
        return None
    return NotificationService.create_notification(
        recipient=task.assigned_to.user,
        title=f"New Task Assigned: {task.title}",
        message=f"You have been assigned a new task by {assigned_by.get_full_name()}",
        notification_type=Notification.NotificationType.TASK,
        related_object=task,
        action_url=f"/erp/tasks/{task.id}/",
    )


def notify_leave_request(leave_request):
    """Notify manager of leave request."""
    if leave_request.employee.reports_to:
        return NotificationService.create_notification(
            recipient=leave_request.employee.reports_to.user,
            title=f"Leave Request: {leave_request.employee.full_name}",
            message=f"{leave_request.employee.full_name} has requested {leave_request.days_requested} days of {leave_request.leave_type.name}",
            notification_type=Notification.NotificationType.APPROVAL,
            related_object=leave_request,
            action_url=f"/erp/leave-requests/{leave_request.id}/",
        )


def notify_expense_approval(expense):
    """Notify user of expense approval/rejection."""
    if not expense.employee or not expense.employee.user:
        return None
    return NotificationService.create_notification(
        recipient=expense.employee.user,
        title=f"Expense {expense.status.title()}: {expense.expense_number}",
        message=f"Your expense claim {expense.expense_number} has been {expense.status}",
        notification_type=Notification.NotificationType.INFO,
        related_object=expense,
        action_url=f"/erp/expenses/{expense.id}/",
    )


def notify_invoice_paid(invoice):
    """Notify of invoice payment."""
    return NotificationService.create_notification(
        recipient=invoice.created_by,
        title=f"Invoice Paid: {invoice.invoice_number}",
        message=f"Invoice {invoice.invoice_number} for {invoice.customer.name} has been fully paid",
        notification_type=Notification.NotificationType.SUCCESS,
        related_object=invoice,
        action_url=f"/erp/invoices/{invoice.id}/",
    )
