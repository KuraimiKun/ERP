"""
ERP Views – Attendance Devices & QR Kiosk

Management views for attendance kiosk devices and the public-facing
kiosk display / QR generation endpoints.

Device-binding flow
~~~~~~~~~~~~~~~~~~~
1.  Owner creates a device entry from the management page.
2.  The kiosk URL is opened on a physical TV / tablet.
3.  On first visit the server generates a unique ``device_token``,
    stores it on the ``AttendanceDevice`` row **and** sets it as an
    HTTP-only cookie on the browser.
4.  The kiosk shows a "Pending Approval" screen until the owner
    approves the device from ``/erp/devices/``.
5.  Once approved, only the browser that holds the matching cookie
    can display the QR codes.  If someone opens the URL on a
    different browser, they get a "device not authorised" page.
"""

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from erp.models import AttendanceDevice, Employee
from erp.models.hr import _generate_device_token
from erp.forms import AttendanceDeviceForm
from ._common import (
    render,
    get_object_or_404,
    redirect,
    messages,
    reverse,
    get_user_company,
    staff_member_required,
)

# Name of the cookie set on the physical kiosk device
DEVICE_COOKIE_NAME = "erp_device_token"
DEVICE_COOKIE_MAX_AGE = 365 * 24 * 60 * 60  # 1 year


# ── Device Management (owner/admin only) ────────────────────────────────────


@staff_member_required
def device_list(request):
    """List all attendance kiosk devices for this company."""
    company = get_user_company(request.user)
    devices = AttendanceDevice.objects.filter(company=company).order_by("name")

    pending_count = devices.filter(
        device_token__gt="",
        is_device_approved=False,
    ).count()

    return render(
        request,
        "erp/attendance/device_list.html",
        {
            "devices": devices,
            "pending_count": pending_count,
        },
    )


@staff_member_required
def device_create(request):
    """Register a new attendance device / kiosk."""
    company = get_user_company(request.user)

    if request.method == "POST":
        form = AttendanceDeviceForm(request.POST, company=company)
        if form.is_valid():
            device = form.save(commit=False)
            device.company = company
            device.save()
            messages.success(
                request,
                f'Device "{device.name}" created. Share the kiosk URL with your IT team.',
            )
            return redirect("erp:device_detail", pk=device.pk)
    else:
        form = AttendanceDeviceForm(company=company)

    return render(
        request,
        "erp/attendance/device_form.html",
        {
            "form": form,
            "title": "Add Attendance Device",
            "submit_text": "Create Device",
        },
    )


@staff_member_required
def device_detail(request, pk):
    """Show device details including kiosk URL."""
    company = get_user_company(request.user)
    device = get_object_or_404(AttendanceDevice, pk=pk, company=company)

    # Build the kiosk URL
    kiosk_url = request.build_absolute_uri(reverse("erp:attendance_kiosk", args=[str(device.device_id)]))

    return render(
        request,
        "erp/attendance/device_detail.html",
        {
            "device": device,
            "kiosk_url": kiosk_url,
        },
    )


@staff_member_required
def device_edit(request, pk):
    """Edit an existing attendance device."""
    company = get_user_company(request.user)
    device = get_object_or_404(AttendanceDevice, pk=pk, company=company)

    if request.method == "POST":
        form = AttendanceDeviceForm(request.POST, instance=device, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, f'Device "{device.name}" updated.')
            return redirect("erp:device_detail", pk=device.pk)
    else:
        form = AttendanceDeviceForm(instance=device, company=company)

    return render(
        request,
        "erp/attendance/device_form.html",
        {
            "form": form,
            "device": device,
            "title": f"Edit Device: {device.name}",
            "submit_text": "Save Changes",
        },
    )


@staff_member_required
def device_delete(request, pk):
    """Delete an attendance device."""
    company = get_user_company(request.user)
    device = get_object_or_404(AttendanceDevice, pk=pk, company=company)

    if request.method == "POST":
        name = device.name
        device.delete()
        messages.success(request, f'Device "{name}" deleted.')
        return redirect("erp:device_list")

    return render(
        request,
        "erp/confirm_delete.html",
        {
            "object": device,
            "object_type": "Attendance Device",
            "cancel_url": reverse("erp:device_detail", args=[pk]),
        },
    )


# ── Kiosk Display & QR API (public – device-cookie-authenticated) ───────────


def _get_client_ip(request):
    """Extract client IP from request, respecting X-Forwarded-For."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _setup_tenant_context_for_device(device_id):
    """
    Find which tenant database houses the given device and activate it.

    Called from public (unauthenticated) kiosk views where no user session
    carries the tenant context.  Scans all active TenantDatabase entries.

    Returns the ``AttendanceDevice`` instance on success, or ``None``.
    """
    from tenants.models import TenantDatabase
    from tenants.routers import set_current_db_alias, add_tenant_database
    from django.conf import settings as _settings

    for tdb in TenantDatabase.objects.using("default").filter(status="active"):
        db_alias = f"tenant_{tdb.id}"
        if db_alias not in _settings.DATABASES:
            add_tenant_database(tdb)

        try:
            device = AttendanceDevice.objects.using(db_alias).get(
                device_id=device_id,
                is_active=True,
            )
            set_current_db_alias(db_alias)
            return device
        except AttendanceDevice.DoesNotExist:
            continue

    return None


def attendance_kiosk(request, device_id):
    """
    Public kiosk page – cookie-token device authentication.

    Flow:
    * First visit  → generate token, store on device row & set cookie,
                      show "waiting for approval" page.
    * Revisit (pending) → show "waiting for approval" page.
    * Revisit (approved) → show QR kiosk.
    * Wrong / missing cookie → show "not authorised" page.
    """
    device = _setup_tenant_context_for_device(device_id)
    if not device:
        from django.http import Http404

        raise Http404("Device not found")

    cookie_token = request.COOKIES.get(DEVICE_COOKIE_NAME, "")

    # ── First-ever visit: no token on the device row yet ────────────────
    if not device.device_token:
        # Generate a new token
        token = _generate_device_token()
        device.device_token = token
        device.is_device_approved = False
        device.device_user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]
        device.device_ip = _get_client_ip(request)
        device.approval_requested_at = timezone.now()
        device.save(
            update_fields=[
                "device_token",
                "is_device_approved",
                "device_user_agent",
                "device_ip",
                "approval_requested_at",
            ]
        )
        # Set cookie on the response
        response = render(
            request,
            "erp/attendance/kiosk_pending.html",
            {
                "device": device,
                "company_name": device.company.name,
            },
        )
        response.set_cookie(
            DEVICE_COOKIE_NAME,
            token,
            max_age=DEVICE_COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
        )
        return response

    # ── Returning visit: cookie must match the stored token ─────────────
    if cookie_token != device.device_token:
        # Different browser / device → reject
        return render(
            request,
            "erp/attendance/kiosk_unauthorised.html",
            {
                "device": device,
                "company_name": device.company.name,
            },
        )

    # Update heartbeat
    AttendanceDevice.objects.filter(pk=device.pk).update(
        last_heartbeat=timezone.now(),
    )

    # ── Pending approval ────────────────────────────────────────────────
    if not device.is_device_approved:
        return render(
            request,
            "erp/attendance/kiosk_pending.html",
            {
                "device": device,
                "company_name": device.company.name,
            },
        )

    # ── Approved → show QR kiosk ────────────────────────────────────────
    return render(
        request,
        "erp/attendance/kiosk.html",
        {
            "device": device,
            "company_name": device.company.name,
            "refresh_seconds": device.qr_refresh_seconds,
        },
    )


@require_GET
def attendance_qr_data(request, device_id):
    """
    AJAX endpoint called by the kiosk JS to get a fresh QR payload.

    Protected: only the browser holding the correct cookie can fetch data.
    """
    device = _setup_tenant_context_for_device(device_id)
    if not device:
        return JsonResponse({"error": "Device not found"}, status=404)

    # Verify cookie
    cookie_token = request.COOKIES.get(DEVICE_COOKIE_NAME, "")
    if not device.device_token or cookie_token != device.device_token:
        return JsonResponse({"error": "Not authorised"}, status=403)
    if not device.is_device_approved:
        return JsonResponse({"error": "Device pending approval"}, status=403)

    payload = device.generate_qr_payload()
    scan_url = request.build_absolute_uri(reverse("erp:attendance_scan_result") + f"?qr={payload['data']}")

    # Update heartbeat
    AttendanceDevice.objects.filter(pk=device.pk).update(
        last_heartbeat=timezone.now(),
    )

    return JsonResponse(
        {
            "qr_data": payload["data"],
            "scan_url": scan_url,
            "expires": payload["expires"],
        }
    )


# ── Device approval / revocation (owner) ────────────────────────────────────


@staff_member_required
@require_POST
def device_approve(request, pk):
    """Approve a pending physical device."""
    company = get_user_company(request.user)
    device = get_object_or_404(AttendanceDevice, pk=pk, company=company)

    device.is_device_approved = True
    device.save(update_fields=["is_device_approved"])
    messages.success(request, f'Device "{device.name}" has been approved.')
    return redirect("erp:device_list")


@staff_member_required
@require_POST
def device_revoke(request, pk):
    """
    Revoke a device's approval and clear its token.

    The physical device will need to reconnect and be re-approved.
    """
    company = get_user_company(request.user)
    device = get_object_or_404(AttendanceDevice, pk=pk, company=company)

    device.device_token = ""
    device.is_device_approved = False
    device.device_user_agent = ""
    device.device_ip = None
    device.approval_requested_at = None
    device.save(
        update_fields=[
            "device_token",
            "is_device_approved",
            "device_user_agent",
            "device_ip",
            "approval_requested_at",
        ]
    )
    messages.success(request, f'Device "{device.name}" has been revoked. It must reconnect to be re-approved.')
    return redirect("erp:device_list")


# ── Invite Links Management (owner only) ────────────────────────────────────


@staff_member_required
def invite_link_list(request):
    """List all employee invite links for the current owner."""
    from tenants.models import EmployeeInviteLink

    user = request.user
    company = get_user_company(user)

    # Get invite links created by THIS user (from default DB)
    links = (
        EmployeeInviteLink.objects.using("default")
        .filter(
            created_by=user,
        )
        .order_by("-created_at")
    )

    return render(
        request,
        "erp/employees/invite_links.html",
        {
            "links": links,
            "company": company,
        },
    )


@staff_member_required
def invite_link_create(request):
    """Generate a new employee invite link."""
    from tenants.models import EmployeeInviteLink

    user = request.user
    company = get_user_company(user)
    tenant_db = user.assigned_database

    if not tenant_db:
        messages.error(request, "No database assigned to your account.")
        return redirect("erp:invite_link_list")

    if request.method == "POST":
        link = EmployeeInviteLink(
            database=tenant_db,
            created_by=user,
            company_name=company.name if company else user.company_name,
            company_name_ar=getattr(company, "name_ar", "") if company else "",
        )
        max_reg = request.POST.get("max_registrations", "0")
        try:
            link.max_registrations = int(max_reg)
        except (ValueError, TypeError):
            link.max_registrations = 0

        expires_days = request.POST.get("expires_days", "")
        if expires_days:
            try:
                from datetime import timedelta

                link.expires_at = timezone.now() + timedelta(days=int(expires_days))
            except (ValueError, TypeError):
                pass

        link.save(using="default")
        messages.success(request, "Invite link created successfully.")
        return redirect("erp:invite_link_list")

    return render(
        request,
        "erp/employees/invite_link_form.html",
        {
            "company": company,
        },
    )


@staff_member_required
def invite_link_toggle(request, pk):
    """Activate / deactivate an invite link."""
    from tenants.models import EmployeeInviteLink

    link = get_object_or_404(
        EmployeeInviteLink.objects.using("default"),
        pk=pk,
        created_by=request.user,
    )
    if request.method == "POST":
        link.is_active = not link.is_active
        link.save(using="default", update_fields=["is_active"])
        status = "activated" if link.is_active else "deactivated"
        messages.success(request, f"Link {status}.")
    return redirect("erp:invite_link_list")


# ── Pending Employee Approvals ──────────────────────────────────────────────


@staff_member_required
def pending_employees(request):
    """List employees awaiting approval."""
    company = get_user_company(request.user)
    pending = Employee.objects.filter(
        company=company,
        approval_status="pending",
    ).order_by("-created_at")

    return render(
        request,
        "erp/employees/pending_list.html",
        {
            "pending_employees": pending,
        },
    )


@staff_member_required
def approve_employee(request, pk):
    """Approve or reject a pending employee registration."""
    from tenants.models import TenantUser, DatabaseAssignment
    from tenants.routers import get_current_db_alias

    company = get_user_company(request.user)
    employee = get_object_or_404(
        Employee,
        pk=pk,
        company=company,
        approval_status="pending",
    )

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "approve":
            employee.approval_status = "approved"

            if employee.company is None:
                employee.company = company

            # Generate proper employee ID
            from erp.services.sequence import SequenceService

            try:
                employee.employee_id = SequenceService.get_next_number(
                    company,
                    "employee",
                )
            except Exception:
                pass  # Keep existing ID

            employee.save()

            # Activate the TenantUser in default DB
            if employee.user_id:
                TenantUser.objects.using("default").filter(
                    pk=employee.user_id,
                ).update(
                    is_approved=True,
                    approval_status="approved",
                    approved_by=request.user,
                    approved_at=timezone.now(),
                )
                # Also update tenant DB copy
                db_alias = get_current_db_alias()
                if db_alias != "default":
                    TenantUser.objects.using(db_alias).filter(
                        pk=employee.user_id,
                    ).update(
                        is_approved=True,
                        approval_status="approved",
                    )

                # Activate DatabaseAssignment
                DatabaseAssignment.objects.using("default").filter(
                    user_id=employee.user_id,
                    is_active=False,
                ).update(is_active=True)

            messages.success(request, f"{employee.full_name} has been approved.")

        elif action == "reject":
            employee.approval_status = "rejected"
            employee.save()

            reason = request.POST.get("reason", "")

            if employee.user_id:
                TenantUser.objects.using("default").filter(
                    pk=employee.user_id,
                ).update(
                    is_approved=False,
                    approval_status="rejected",
                    rejection_reason=reason,
                )

            messages.warning(request, f"{employee.full_name} has been rejected.")

        return redirect("erp:pending_employees")

    return render(
        request,
        "erp/employees/approve_form.html",
        {
            "employee": employee,
        },
    )
