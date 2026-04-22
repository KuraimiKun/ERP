"""
Admin Mobile API package.

A mobile-optimised, admin-scoped REST API mounted at
``/api/mobile/admin/v1/``.  Consumed by the Flutter admin app; the usage
guide lives in ``docs/admin_mobile_api.md``.

This package intentionally does **not** reimplement business logic —
every mutation delegates to the existing service layer (e.g.
``erp.services.accounting.create_*_journal_entry``) so bookkeeping,
auditing and state machines stay consistent with the web API.
"""
