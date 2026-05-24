"""
Platform Admin - Database Management Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q, F
from django.views.decorators.http import require_POST, require_http_methods

from tenants.models import (
    TenantUser,
    PostgresServer,
    TenantDatabase,
    DatabaseAssignment,
    ServerLog,
    EmployeeInviteLink,
)
from tenants.platform_admin.forms import PlatformAdminDatabaseCreateForm
from . import platform_admin_required, pa_context, paginate


@platform_admin_required
def pa_database_list(request):
    """List all tenant databases."""
    qs = (
        TenantDatabase.objects.select_related("server", "created_by")
        .annotate(
            user_count=Count("assignments", filter=Q(assignments__is_active=True)),
        )
        .order_by("-created_at")
    )

    # Filters
    status = request.GET.get("status")
    if status in ("creating", "active", "suspended", "error", "deleted"):
        qs = qs.filter(status=status)

    server_id = request.GET.get("server")
    if server_id:
        qs = qs.filter(server_id=server_id)

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(display_name__icontains=search))

    page = paginate(request, qs)

    context = pa_context(
        request,
        {
            "databases": page,
            "current_status": status,
            "search_query": search,
            "servers": PostgresServer.objects.all(),
            "status_counts": {
                "all": TenantDatabase.objects.count(),
                "active": TenantDatabase.objects.filter(status="active").count(),
                "creating": TenantDatabase.objects.filter(status="creating").count(),
                "suspended": TenantDatabase.objects.filter(status="suspended").count(),
                "error": TenantDatabase.objects.filter(status="error").count(),
            },
        },
    )
    return render(request, "platform_admin/databases/list.html", context)


@platform_admin_required
def pa_database_detail(request, pk):
    """Detailed view of a tenant database."""
    database = get_object_or_404(TenantDatabase.objects.select_related("server", "created_by"), pk=pk)
    assignments = (
        DatabaseAssignment.objects.filter(database=database)
        .select_related("user", "assigned_by")
        .order_by("-assigned_at")
    )
    logs = ServerLog.objects.filter(database=database).order_by("-created_at")[:20]
    invite_links = EmployeeInviteLink.objects.filter(database=database).order_by("-created_at")

    context = pa_context(
        request,
        {
            "database": database,
            "assignments": assignments,
            "logs": logs,
            "invite_links": invite_links,
        },
    )
    return render(request, "platform_admin/databases/detail.html", context)


@platform_admin_required
@require_POST
def pa_database_migrate(request, pk):
    """Run migrations on a tenant database."""
    database = get_object_or_404(TenantDatabase, pk=pk)

    try:
        from tenants.services import DatabaseService

        db_service = DatabaseService()
        db_service.run_migrations(database)
        database.is_migrated = True
        database.migrated_at = timezone.now()
        database.save()

        ServerLog.objects.create(
            server=database.server,
            database=database,
            user=request.user,
            action="database_migrate",
            level="success",
            message=f"Migrations completed for {database.name}.",
        )
        messages.success(request, _("Migrations completed successfully."))
    except Exception as e:
        ServerLog.objects.create(
            server=database.server,
            database=database,
            user=request.user,
            action="database_migrate",
            level="error",
            message=f"Migration failed: {e}",
        )
        messages.error(request, _(f"Migration failed: {e}"))

    return redirect("tenants:pa_database_detail", pk=pk)


@platform_admin_required
@require_POST
def pa_database_test(request, pk):
    """Test connection to a tenant database."""
    database = get_object_or_404(TenantDatabase, pk=pk)

    try:
        from tenants.services import DatabaseService

        db_service = DatabaseService()
        is_ok = db_service.test_database_connection(database)
        if is_ok:
            messages.success(request, _("Database connection test passed."))
        else:
            messages.error(request, _("Database connection test failed."))
    except Exception as e:
        messages.error(request, _(f"Connection test error: {e}"))

    return redirect("tenants:pa_database_detail", pk=pk)


@platform_admin_required
@require_http_methods(["GET", "POST"])
def pa_database_create(request):
    """Create a new tenant database on a server."""
    form = PlatformAdminDatabaseCreateForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            try:
                from tenants.services import DatabaseService

                server = form.cleaned_data["server"]
                tenant_db = DatabaseService().create_tenant_database(
                    server=server,
                    name=form.cleaned_data.get("name"),
                    display_name=form.cleaned_data.get("display_name"),
                    created_by=request.user,
                )

                assign_user = form.cleaned_data.get("assign_user")
                if assign_user:
                    DatabaseAssignment.objects.create(
                        user=assign_user,
                        database=tenant_db,
                        role=form.cleaned_data.get("role") or "owner",
                        assigned_by=request.user,
                    )

                messages.success(request, _("Database created successfully."))
                return redirect("tenants:pa_database_detail", pk=tenant_db.pk)
            except Exception as e:
                messages.error(request, _("Failed to create database: %(error)s") % {"error": str(e)})
        else:
            messages.error(request, _("Please correct the errors below."))

    context = pa_context(
        request,
        {
            "form": form,
            "has_available_servers": form.fields["server"].queryset.exists(),
        },
    )
    return render(request, "platform_admin/databases/create.html", context)


@platform_admin_required
@require_POST
def pa_database_suspend(request, pk):
    """Suspend a tenant database."""
    database = get_object_or_404(TenantDatabase, pk=pk)
    database.status = "suspended"
    database.save()

    # Deactivate all assignments
    DatabaseAssignment.objects.filter(database=database, is_active=True).update(
        is_active=False, deactivated_at=timezone.now()
    )

    ServerLog.objects.create(
        server=database.server,
        database=database,
        user=request.user,
        action="database_delete",
        level="warning",
        message=f"Database {database.name} suspended.",
    )
    messages.success(request, _("Database has been suspended."))
    return redirect("tenants:pa_database_detail", pk=pk)


@platform_admin_required
@require_POST
def pa_database_activate(request, pk):
    """Reactivate a suspended database."""
    database = get_object_or_404(TenantDatabase, pk=pk)
    database.status = "active"
    database.save()

    ServerLog.objects.create(
        server=database.server,
        database=database,
        user=request.user,
        action="database_create",
        level="success",
        message=f"Database {database.name} reactivated.",
    )
    messages.success(request, _("Database has been reactivated."))
    return redirect("tenants:pa_database_detail", pk=pk)


@platform_admin_required
@require_POST
def pa_database_delete(request, pk):
    """Delete a tenant database permanently."""
    database = get_object_or_404(TenantDatabase, pk=pk)
    name = database.name
    server = database.server

    # Deactivate all assignments first
    DatabaseAssignment.objects.filter(database=database).update(is_active=False, deactivated_at=timezone.now())

    # Try to drop the actual database
    try:
        from tenants.services import DatabaseService

        db_service = DatabaseService()
        db_service.drop_tenant_database(database)
    except Exception:
        pass  # Log but don't block deletion

    ServerLog.objects.create(
        server=server,
        user=request.user,
        action="database_delete",
        level="warning",
        message=f"Database {name} deleted.",
    )

    database.status = "deleted"
    database.save()

    messages.success(request, _(f'Database "{name}" has been deleted.'))
    return redirect("tenants:pa_database_list")
