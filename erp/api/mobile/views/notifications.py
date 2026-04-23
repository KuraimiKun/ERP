"""Notification endpoints."""

from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from erp.models import Notification


@api_view(['GET'])
def mobile_notifications(request):
    """List notifications for the user."""
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).order_by('-created_at')[:50]

    return Response({
        'notifications': [{
            'id': n.pk,
            'type': n.notification_type,
            'title': n.title,
            'message': n.message,
            'is_read': n.is_read,
            'created_at': n.created_at.isoformat(),
            'action_url': n.action_url or '',
        } for n in notifications],
        'unread_count': Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count(),
    })


@api_view(['POST'])
def mobile_notifications_read(request):
    """Mark notification(s) as read."""
    notification_ids = request.data.get('ids', [])
    mark_all = request.data.get('all', False)

    if mark_all:
        Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).update(is_read=True, read_at=timezone.now())
    elif notification_ids:
        Notification.objects.filter(
            recipient=request.user, pk__in=notification_ids,
        ).update(is_read=True, read_at=timezone.now())

    return Response({'success': True})
