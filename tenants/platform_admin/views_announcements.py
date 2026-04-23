"""
Platform Admin - System Announcements Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from tenants.models import Announcement
from .forms import AnnouncementForm
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_announcement_list(request):
    """List all announcements."""
    qs = Announcement.objects.select_related("created_by")

    ann_type = request.GET.get("type")
    status = request.GET.get("status")
    if ann_type:
        qs = qs.filter(announcement_type=ann_type)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    page_obj = paginate(request, qs, 20)

    active_count = Announcement.objects.filter(is_active=True).count()
    total_count = Announcement.objects.count()

    context = pa_context(
        request,
        {
            "announcements": page_obj,
            "current_type": ann_type,
            "current_status": status,
            "active_count": active_count,
            "total_count": total_count,
            "type_choices": Announcement.TYPE_CHOICES,
        },
    )
    return render(request, "platform_admin/announcements/list.html", context)


@platform_admin_required
def pa_announcement_create(request):
    """Create a new announcement."""
    if request.method == "POST":
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            ann = form.save(commit=False)
            ann.created_by = request.user
            ann.save()
            messages.success(request, _("Announcement created."))
            return redirect("tenants:pa_announcement_list")
    else:
        form = AnnouncementForm()

    context = pa_context(request, {"form": form})
    return render(request, "platform_admin/announcements/form.html", context)


@platform_admin_required
def pa_announcement_edit(request, pk):
    """Edit an existing announcement."""
    ann = get_object_or_404(Announcement, pk=pk)
    if request.method == "POST":
        form = AnnouncementForm(request.POST, instance=ann)
        if form.is_valid():
            form.save()
            messages.success(request, _("Announcement updated."))
            return redirect("tenants:pa_announcement_list")
    else:
        form = AnnouncementForm(instance=ann)

    context = pa_context(request, {"form": form, "announcement": ann, "editing": True})
    return render(request, "platform_admin/announcements/form.html", context)


@platform_admin_required
def pa_announcement_detail(request, pk):
    """Detail view of an announcement."""
    ann = get_object_or_404(Announcement.objects.select_related("created_by"), pk=pk)
    dismissals = ann.dismissals.select_related("user").order_by("-dismissed_at")[:50]
    dismiss_count = ann.dismissals.count()

    context = pa_context(
        request,
        {
            "announcement": ann,
            "dismissals": dismissals,
            "dismiss_count": dismiss_count,
        },
    )
    return render(request, "platform_admin/announcements/detail.html", context)


@platform_admin_required
@require_POST
def pa_announcement_toggle(request, pk):
    """Toggle announcement active status."""
    ann = get_object_or_404(Announcement, pk=pk)
    ann.is_active = not ann.is_active
    ann.save(update_fields=["is_active"])
    status_text = _("activated") if ann.is_active else _("deactivated")
    messages.success(request, _(f'Announcement "{ann.title}" {status_text}.'))
    return redirect("tenants:pa_announcement_list")


@platform_admin_required
@require_POST
def pa_announcement_delete(request, pk):
    """Delete an announcement."""
    ann = get_object_or_404(Announcement, pk=pk)
    title = ann.title
    ann.delete()
    messages.success(request, _(f'Announcement "{title}" deleted.'))
    return redirect("tenants:pa_announcement_list")


@platform_admin_required
@require_POST
def pa_announcement_pin(request, pk):
    """Toggle pin status."""
    ann = get_object_or_404(Announcement, pk=pk)
    ann.is_pinned = not ann.is_pinned
    ann.save(update_fields=["is_pinned"])
    msg = _("Announcement pinned.") if ann.is_pinned else _("Announcement unpinned.")
    messages.success(request, msg)
    return redirect("tenants:pa_announcement_list")
