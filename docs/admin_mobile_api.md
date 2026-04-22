# Admin Mobile API

A mobile-optimised REST API for company admins, consumed by the Flutter
admin app. All endpoints live under `/api/mobile/admin/v1/`.

This document covers the full admin mobile API. Endpoints are grouped
by concern (auth, dashboard, approvals, masters, reports, …) and all
live beneath `/api/mobile/admin/v1/`.

## Base URL and versioning

```
/api/mobile/admin/v1/
```

The `v1/` segment is kept in the path from day one so breaking changes
can ship at `/api/mobile/admin/v2/` without disturbing existing
installations.

## Authentication

Clients authenticate with DRF token auth using the header:

```
Authorization: Token <token-key>
```

Tokens are obtained from the existing employee mobile login
(`POST /api/mobile/auth/login/`). The admin mobile API reuses that
token; it does not mint a separate token type in v1 (this may change in
a future iteration — see the "Open questions" section of the plan).

Token lookups always read from the `default` database (see
`DefaultDbTokenAuthentication`) so they succeed regardless of which
tenant database the request is routed to.

## Tenant routing

The request's tenant database is resolved from the authenticated user's
active `DatabaseAssignment`. Platform-support callers who need to act
against a specific tenant may pass:

```
X-Tenant-DB: tenant_<uuid>
```

Non-superusers can only target their own assigned tenant DB; other
values are ignored and the request falls back to the user's default
assignment.

## Authorisation

Every admin mobile endpoint requires the caller to satisfy the
`IsCompanyAdmin` permission:

* `request.user.is_superuser`, **or**
* The user has an `employee_profile` linked to a company **and** an
  active `tenants.DatabaseAssignment` with `role in {'owner', 'admin'}`.

Failures return HTTP 403 with a JSON body of the form
`{"detail": "Admin access required. …"}`.

## Pagination

List endpoints use `AdminMobilePagination` (a `PageNumberPagination`):

| Query param | Default | Max |
|-------------|---------|-----|
| `page`      | 1       | —   |
| `page_size` | 25      | 100 |

Responses follow the DRF default shape:

```json
{
  "count": 123,
  "next": "https://…?page=2",
  "previous": null,
  "results": [ … ]
}
```

## Error envelope

Errors follow DRF's conventions:

| Status | Shape                                                    |
|--------|----------------------------------------------------------|
| 400    | `{"field": ["message"]}` or `{"detail": "…"}`            |
| 401    | `{"detail": "Authentication credentials were not provided."}` |
| 403    | `{"detail": "Admin access required. …"}`                 |
| 404    | `{"detail": "Not found."}`                               |

## Endpoint catalogue

Unless noted, every endpoint requires `IsCompanyAdmin` and returns
company-scoped data. Serializer shapes live in
`erp.api.admin_mobile.serializers`.

### Auth & session

| Method | Path | Purpose |
|--------|------|---------|
| POST   | `/auth/login/`           | Email + password → DRF token, role, employee, company, feature flags. |
| POST   | `/auth/logout/`          | Invalidate the caller's token. |
| GET    | `/auth/me/`              | Who am I? Returns user/employee/company/role. |
| POST   | `/auth/change-password/` | Rotate the caller's password. |
| POST   | `/devices/register/`     | Register an FCM / APNs device token (`platform ∈ {android, ios}`). |

### Dashboard

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/dashboard/`          | Today revenue, cash-in-hand, pending approval counts, low-stock items, open POS sessions, overdue invoice amount, month-to-date revenue/expenses. Cached 5 min per company. |
| GET | `/dashboard/activity/` | Recent activity timeline (invoices, POs, leaves, notifications). |
| GET | `/dashboard/kpis/`     | 30-day KPIs: revenue, expenses, net, new customers, new leads, invoices issued, payments received. |

### Approval queues

Each viewset lists only **pending** objects and exposes `approve`/`reject`
detail-actions. Expense and supplier-invoice approval post journal
entries via `erp.services.accounting`/`erp.services.inventory_accounting`.

| Path | Actions |
|------|---------|
| `/leaves/pending/`             | `GET /`, `POST /{id}/approve/`, `POST /{id}/reject/` |
| `/expenses/pending/`           | same |
| `/purchase-orders/pending/`    | same |
| `/quotes/pending/`             | same |
| `/supplier-invoices/pending/`  | same |

### Masters — CRUD

Standard DRF CRUD (`list`, `retrieve`, `create`, `update`, `partial_update`,
`destroy`) against the following routes. List responses use compact
mobile serializers; detail/create/update reuse the v1 serializers.
Deletes are soft-deletes via `ERPBaseModel.soft_delete`.

HR: `/employees/`, `/departments/`, `/branches/`, `/attendance/`,
`/leave-requests/`, `/payroll/`
Finance: `/customers/`, `/invoices/`, `/payments/`, `/expenses/`;
read-only `/accounts/`, `/tax-rates/`
Supplier: `/suppliers/`, `/purchase-orders/`, `/supplier-invoices/`,
`/supplier-payments/`
Inventory: `/warehouses/`, `/products/`, `/goods-receipts/`,
`/stock-adjustments/`; read-only `/stock-items/`, `/stock-movements/`
POS: `/pos/terminals/`, `/pos/sessions/` (+ `POST /pos/sessions/{id}/close/`),
read-only `/pos/orders/`
CRM: `/leads/`, `/lead-activities/`, `/customer-interactions/`,
`/tasks/`, `/campaigns/`
Services: `/quotes/`, read-only `/service-pricing/`

### Reports

All reports return JSON, with `Decimal` fields serialised as strings.
Financial reports delegate to `erp.services.financial_reports` so the
numbers match `/api/finance/reports/*` exactly.

| Method | Path | Query | Returns |
|--------|------|-------|---------|
| GET | `/reports/trial-balance/`     | `start`, `end` (ISO) | Trial balance for the period (falls back to the active fiscal year). |
| GET | `/reports/profit-and-loss/`   | `start`, `end`       | P&L for the period. |
| GET | `/reports/balance-sheet/`     | `as_of` (ISO)        | Balance sheet at a point in time. |
| GET | `/reports/cash-flow/`         | `start`, `end`       | Cash flow for the period. |
| GET | `/reports/sales-summary/`     | `period ∈ {day,week,month,year}` | Revenue, paid, outstanding, count. |
| GET | `/reports/top-products/`      | `period`, `limit`    | Top products by revenue (POS). |
| GET | `/reports/top-customers/`     | `period`, `limit`    | Top customers by revenue. |
| GET | `/reports/aging-receivables/` | —                    | 0–30, 31–60, 61–90, 90+ aging buckets for customer invoices. |
| GET | `/reports/aging-payables/`    | —                    | Same buckets for supplier invoices. |

### Notifications, audit, search, settings

| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/notifications/`                 | Inbox (`?unread=1` filter). |
| POST | `/notifications/read/`            | `{"ids":[...]}` marks listed notifications read. |
| POST | `/notifications/read-all/`        | Mark every notification read. |
| GET  | `/notifications/unread-count/`    | `{"count": N}`. |
| GET  | `/audit-logs/`                    | Audit entries (`?model=`, `?since=`, `?actor=`, `?action=`). |
| GET  | `/search/?q=&types=`              | Federated search over employees/customers/products/invoices. |
| GET \| PATCH | `/company/`               | Read or update a whitelisted subset of the caller's company (`name`, `name_ar`, `email`, `phone`, `address`, `city`, `country`). |
| GET  | `/company/feature-flags/`         | `{"ai_enabled": bool}`. |
| GET  | `/fiscal-years/`                  | Read-only list. |
| GET  | `/currencies/`                    | Read-only list (not company-scoped). |

## OpenAPI / Swagger

All admin mobile endpoints are tagged `admin-mobile` in the generated
OpenAPI schema (`/api/schema/`, `/api/docs/`, `/api/redoc/`). The Flutter
team can generate a typed client directly from that schema.
