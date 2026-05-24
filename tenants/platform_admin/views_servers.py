"""
Platform Admin - Server Management Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Q
from django.views.decorators.http import require_POST, require_http_methods

from tenants.models import PostgresServer, TenantDatabase, ServerLog
from tenants.platform_admin.forms import PostgresServerForm
from . import platform_admin_required, pa_context


@platform_admin_required
def pa_server_list(request):
    """List all PostgreSQL servers."""
    servers = PostgresServer.objects.annotate(
        db_count=Count("databases"),
        active_db_count=Count("databases", filter=Q(databases__status="active")),
        user_count=Count("databases__assignments", filter=Q(databases__assignments__is_active=True)),
    ).order_by("name")

    context = pa_context(
        request,
        {
            "servers": servers,
        },
    )
    return render(request, "platform_admin/servers/list.html", context)


@platform_admin_required
def pa_server_detail(request, pk):
    """Detailed view of a server."""
    server = get_object_or_404(PostgresServer, pk=pk)
    databases = (
        TenantDatabase.objects.filter(server=server)
        .annotate(
            user_count=Count("assignments", filter=Q(assignments__is_active=True)),
        )
        .order_by("-created_at")
    )
    logs = ServerLog.objects.filter(server=server).order_by("-created_at")[:30]

    context = pa_context(
        request,
        {
            "server": server,
            "databases": databases,
            "logs": logs,
        },
    )
    return render(request, "platform_admin/servers/detail.html", context)


@platform_admin_required
@require_POST
def pa_server_health_check(request, pk):
    """Run a health check on a server."""
    server = get_object_or_404(PostgresServer, pk=pk)

    try:
        from tenants.services import DatabaseService

        db_service = DatabaseService()
        is_healthy = db_service.check_server_health(server)

        server.last_health_check = timezone.now()
        if is_healthy:
            server.status = "active"
            server.health_check_message = "Server is healthy and responding."
            messages.success(request, _("Server health check passed."))
        else:
            server.status = "error"
            server.health_check_message = "Server is not responding."
            messages.error(request, _("Server health check failed."))
        server.save()

        ServerLog.objects.create(
            server=server,
            user=request.user,
            action="server_health_check",
            level="success" if is_healthy else "error",
            message=server.health_check_message,
        )
    except Exception as e:
        server.last_health_check = timezone.now()
        server.status = "error"
        server.health_check_message = str(e)
        server.save()
        messages.error(request, _(f"Health check error: {e}"))

    return redirect("tenants:pa_server_detail", pk=pk)


@platform_admin_required
@require_POST
def pa_server_toggle(request, pk):
    """Start or stop a Docker server."""
    server = get_object_or_404(PostgresServer, pk=pk)
    action = request.POST.get("action", "start")

    if server.server_type != "docker":
        messages.error(request, _("Can only start/stop Docker servers."))
        return redirect("tenants:pa_server_detail", pk=pk)

    try:
        from tenants.services import DockerService

        docker_service = DockerService()

        if action == "start":
            docker_service.start_container(server.docker_container_name)
            server.status = "active"
            server.save()
            ServerLog.objects.create(
                server=server,
                user=request.user,
                action="server_start",
                level="success",
                message=f"Server {server.name} started.",
            )
            messages.success(request, _("Server started successfully."))
        elif action == "stop":
            docker_service.stop_container(server.docker_container_name)
            server.status = "inactive"
            server.save()
            ServerLog.objects.create(
                server=server,
                user=request.user,
                action="server_stop",
                level="success",
                message=f"Server {server.name} stopped.",
            )
            messages.success(request, _("Server stopped successfully."))
    except Exception as e:
        messages.error(request, _(f"Operation failed: {e}"))

    return redirect("tenants:pa_server_detail", pk=pk)


@platform_admin_required
@require_http_methods(["GET", "POST"])
def pa_server_create(request):
    """Create a new PostgreSQL server."""
    form = PostgresServerForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            try:
                cleaned = form.cleaned_data
                if cleaned["server_type"] == "docker":
                    from tenants.services.docker_service import DockerService

                    docker_service = DockerService()
                    safe_name = cleaned["name"].lower()
                    server = docker_service.create_postgres_container(
                        name=cleaned["name"],
                        description=cleaned.get("description", ""),
                        container_name=f"erp_pg_{''.join(ch if ch.isalnum() or ch in '_-' else '_' for ch in safe_name).strip('_')}",
                        port=cleaned["port"],
                        postgres_password=cleaned["admin_password"],
                        max_databases=cleaned["max_databases"],
                        created_by=request.user,
                    )
                    messages.success(
                        request,
                        _("Docker PostgreSQL server created successfully. Health status has been checked automatically."),
                    )
                else:
                    server = form.save(commit=False)
                    server.created_by = request.user
                    server.save()
                    ServerLog.objects.create(
                        server=server,
                        user=request.user,
                        action="server_create",
                        level="success",
                        message=f'Server "{server.name}" created.',
                    )
                    messages.success(request, _("Server created successfully."))
                return redirect("tenants:pa_server_detail", pk=server.pk)
            except Exception as e:
                messages.error(request, _("Failed to create server: %(error)s") % {"error": str(e)})
        else:
            messages.error(request, _("Please correct the errors below."))

    context = pa_context(
        request,
        {
            "form": form,
        },
    )
    return render(request, "platform_admin/servers/create.html", context)


@platform_admin_required
@require_http_methods(["GET", "POST"])
def pa_server_edit(request, pk):
    """Edit an existing PostgreSQL server."""
    server = get_object_or_404(PostgresServer, pk=pk)
    form = PostgresServerForm(request.POST or None, instance=server)

    if request.method == "POST":
        if form.is_valid():
            try:
                server = form.save()
                messages.success(request, _("Server updated successfully."))
                return redirect("tenants:pa_server_detail", pk=server.pk)
            except Exception as e:
                messages.error(request, _("Failed to update server: %(error)s") % {"error": str(e)})
        else:
            messages.error(request, _("Please correct the errors below."))

    context = pa_context(
        request,
        {
            "server": server,
            "form": form,
        },
    )
    return render(request, "platform_admin/servers/edit.html", context)


@platform_admin_required
@require_POST
def pa_server_delete(request, pk):
    """Delete a server (only if it has no databases)."""
    server = get_object_or_404(PostgresServer, pk=pk)

    if server.databases.exists():
        messages.error(request, _("Cannot delete a server with existing databases. Remove all databases first."))
        return redirect("tenants:pa_server_detail", pk=pk)

    name = server.name
    server.delete()
    messages.success(request, _(f'Server "{name}" has been deleted.'))
    return redirect("tenants:pa_server_list")
