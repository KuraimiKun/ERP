"""
Signals for Tenant Management
"""

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings

from .models import TenantUser, DatabaseAssignment


@receiver(post_save, sender=TenantUser)
def user_status_changed(sender, instance, created, **kwargs):
    """Handle user status changes."""
    if created:
        # New user registered - notify admins
        # You can customize this to send email notifications
        pass
    else:
        # Check if approval status changed
        if instance.approval_status == 'approved' and instance.is_approved:
            # User was approved - could send welcome email
            pass
        elif instance.approval_status == 'rejected':
            # User was rejected - could send notification
            pass


@receiver(post_save, sender=DatabaseAssignment)
def database_assigned(sender, instance, created, **kwargs):
    """Handle new database assignments."""
    if created and instance.is_active:
        # New active assignment created
        # Could send notification to user
        pass
