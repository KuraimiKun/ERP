"""Attendance list and QR-scan endpoints."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from erp.models import Attendance, AttendanceDevice

from ..base import _error, _get_employee


@api_view(["GET"])
def mobile_attendance_list(request):
    """Attendance history with date range filter."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_view_attendance:
        return _error("Permission denied.", 403)

    today = date.today()
    start_date = request.query_params.get("start_date", today.replace(day=1).isoformat())
    end_date = request.query_params.get("end_date", today.isoformat())

    attendances = Attendance.objects.filter(
        employee=employee,
        date__gte=start_date,
        date__lte=end_date,
    ).order_by("-date")

    stats = attendances.aggregate(
        present=Count("id", filter=Q(is_present=True)),
        late=Count("id", filter=Q(is_late=True)),
        absent=Count("id", filter=Q(is_present=False)),
    )

    return Response(
        {
            "stats": stats,
            "start_date": start_date,
            "end_date": end_date,
            "attendances": [
                {
                    "id": a.pk,
                    "date": a.date.isoformat(),
                    "check_in": str(a.check_in) if a.check_in else None,
                    "check_out": str(a.check_out) if a.check_out else None,
                    "hours_worked": str(a.hours_worked),
                    "overtime_hours": str(a.overtime_hours),
                    "is_present": a.is_present,
                    "is_late": a.is_late,
                    "late_minutes": a.late_minutes,
                }
                for a in attendances
            ],
        }
    )


@api_view(["POST"])
def mobile_attendance_scan(request):
    """Process QR code scan for check-in/check-out."""
    employee = _get_employee(request.user)
    if not employee:
        return _error("No employee profile found.", 404)

    if not employee.portal_can_scan_qr:
        return _error("Permission denied.", 403)

    # ── Rate-limit: 1 scan per 30 s per employee ──
    _SCAN_COOLDOWN = 30
    throttle_key = f"qr_scan:{employee.pk}"
    if cache.get(throttle_key):
        return _error("Please wait before scanning again.", 429)

    qr_data = request.data.get("qr_data", "")
    if not qr_data:
        return _error("No QR code data provided.")

    # The kiosk encodes a full URL (scan_url) into the QR image so that
    # browsers can tap it directly.  The mobile app scans the same QR and
    # sends the raw string, which may be the full URL.  Extract the payload
    # from the ?qr= query parameter when present.
    if "?qr=" in qr_data:
        from urllib.parse import urlparse, parse_qs

        qs = parse_qs(urlparse(qr_data).query)
        qr_data = qs.get("qr", [""])[0]

    try:
        device = AttendanceDevice.verify_qr_payload(qr_data, max_age=30)
    except ValueError as e:
        return _error(str(e))

    if employee.company_id != device.company_id:
        return _error("This device does not belong to your company.")

    today = timezone.now().date()
    now_time = timezone.now().time()

    # ── Duplicate check-in guard ──
    existing = Attendance.objects.filter(employee=employee, date=today).first()
    if existing and existing.check_in:
        last_ts = datetime.combine(today, existing.check_out or existing.check_in)
        elapsed = (datetime.combine(today, now_time) - last_ts).total_seconds()
        if elapsed < _SCAN_COOLDOWN:
            return _error("Duplicate scan detected. Try again shortly.", 429)

    # Mark cooldown AFTER validation passes
    cache.set(throttle_key, 1, _SCAN_COOLDOWN)

    attendance, created = Attendance.objects.get_or_create(
        employee=employee,
        date=today,
        defaults={"check_in": now_time, "is_present": True},
    )

    action = "check_in"

    if created:
        if device.work_start_time:
            start_dt = datetime.combine(today, device.work_start_time)
            threshold_dt = start_dt + timedelta(minutes=device.late_threshold_minutes)
            check_in_dt = datetime.combine(today, now_time)
            if check_in_dt > threshold_dt:
                attendance.is_late = True
                attendance.late_minutes = int((check_in_dt - start_dt).total_seconds() / 60)
                attendance.save(update_fields=["is_late", "late_minutes"])
    else:
        action = "check_out"
        attendance.check_out = now_time
        if attendance.check_in:
            cin = datetime.combine(today, attendance.check_in)
            cout = datetime.combine(today, now_time)
            diff = (cout - cin).total_seconds() / 3600
            attendance.hours_worked = Decimal(str(round(diff, 2)))
            if device.work_start_time and device.work_end_time:
                standard = (
                    datetime.combine(today, device.work_end_time) - datetime.combine(today, device.work_start_time)
                ).total_seconds() / 3600
                if diff > standard:
                    attendance.overtime_hours = Decimal(str(round(diff - standard, 2)))
        attendance.save()

    return Response(
        {
            "success": True,
            "action": action,
            "attendance": {
                "id": attendance.pk,
                "date": attendance.date.isoformat(),
                "check_in": str(attendance.check_in) if attendance.check_in else None,
                "check_out": str(attendance.check_out) if attendance.check_out else None,
                "is_present": attendance.is_present,
                "is_late": attendance.is_late,
                "late_minutes": attendance.late_minutes,
                "hours_worked": str(attendance.hours_worked),
                "overtime_hours": str(attendance.overtime_hours),
            },
        }
    )
