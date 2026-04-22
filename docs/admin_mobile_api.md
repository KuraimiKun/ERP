# Admin Mobile API

A mobile-optimised REST API for company admins, consumed by the Flutter
admin app. All endpoints live under `/api/mobile/admin/v1/`.

This document covers what ships in the **Foundation PR**. Later PRs
expand it with auth/dashboard, approval queues, master-data CRUD,
reports, notifications, search, and settings as laid out in the
full implementation plan.

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

## Endpoints shipped by this PR

| Method | Path | Purpose |
|--------|------|---------|
| GET    | `/auth/me/` | Return the authenticated admin — user, employee, company, tenant role. Smoke-test endpoint for the Flutter client. |

## OpenAPI / Swagger

All admin mobile endpoints are tagged `admin-mobile` in the generated
OpenAPI schema (`/api/schema/`, `/api/docs/`, `/api/redoc/`). The Flutter
team can generate a typed client directly from that schema.
