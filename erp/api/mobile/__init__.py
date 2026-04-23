"""
Mobile API package for the Employee Portal Flutter app.

Mounted at ``/api/mobile/``. Endpoints expect Token authentication and
an ``X-Tenant-DB`` header (except login, which resolves the tenant from
the user's DatabaseAssignment).

Layout mirrors ``erp.api.admin_mobile``:

    mobile/
        base.py          shared helpers (_get_employee, _employee_json, _error)
        urls.py          URL patterns
        views/           view modules grouped by domain
            auth.py
            dashboard.py
            profile.py
            attendance.py
            leaves.py
            payslips.py
            tasks.py
            notifications.py
            pos.py

This package does **not** duplicate business logic — every mutation
delegates to the existing service layer (``erp.services.pos``, etc.).
"""
