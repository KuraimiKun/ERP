"""
ERP Views – Notifications

Full-page notification list + AJAX endpoints for the header bell dropdown.
"""

from django.http import JsonResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST

from erp.models import Notification
from erp.services.notification import NotificationService
from ._common import (
    render,
    get_object_or_404,
    staff_member_required,
)


@staff_member_required
def notification_list(request):
    """Full-page notification list."""
    qs = Notification.objects.filter(recipient=request.user).order_by("-created_at")

    filter_type = request.GET.get("type", "")
    if filter_type:
        qs = qs.filter(notification_type=filter_type)

    is_read_param = request.GET.get("is_read", "")
    if is_read_param == "0":
        qs = qs.filter(is_read=False)
    elif is_read_param == "1":
        qs = qs.filter(is_read=True)

    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page", 1))

    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()

    return render(
        request,
        "erp/notifications/list.html",
        {
            "page_obj": page,
            "unread_count": unread_count,
            "current_type": filter_type,
            "current_is_read": is_read_param,
            "notification_types": Notification.NotificationType.choices,
        },
    )


@staff_member_required
def notification_dropdown(request):
    """JSON endpoint for the header bell dropdown (recent + unread count)."""
    recent = NotificationService.get_recent_notifications(request.user, limit=8)
    unread_count = NotificationService.get_unread_count(request.user)

    items = []
    for n in recent:
        items.append(
            {
                "id": n.pk,
                "title": n.title,
                "message": n.message[:120],
                "type": n.notification_type,
                "is_read": n.is_read,
                "action_url": n.action_url or "",
                "created_at": n.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )

    return JsonResponse({"unread_count": unread_count, "items": items})


@require_POST
@staff_member_required
def notification_mark_read(request, pk):
    """Mark a single notification as read."""
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    NotificationService.mark_as_read(notification)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    from django.shortcuts import redirect

    return redirect("erp:notification_list")


@require_POST
@staff_member_required
def notification_mark_all_read(request):
    """Mark all notifications as read."""
    NotificationService.mark_all_as_read(request.user)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True})
    from django.shortcuts import redirect

    return redirect("erp:notification_list")
