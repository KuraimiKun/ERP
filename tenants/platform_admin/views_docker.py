"""
Platform Admin - Docker Enterprise Management Views

Container stats, resource management, image management,
inspection, logs viewer, live terminal, system-wide Docker information.
"""

import json
import shlex

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from tenants.models import PostgresServer, ServerLog
from tenants.services.docker_service import DockerService
from . import platform_admin_required, pa_context


# ── Docker Dashboard ─────────────────────────────────────────────────────────

@platform_admin_required
def pa_docker_dashboard(request):
    """Docker overview: system info, images, all container servers."""
    docker_service = DockerService()
    available = docker_service.is_docker_available()
    system_info = docker_service.get_docker_system_info() if available else {}
    images = docker_service.get_docker_images() if available else []

    docker_servers = PostgresServer.objects.filter(server_type='docker').order_by('name')

    # Get live status for each Docker server
    server_statuses = []
    for s in docker_servers:
        status = docker_service.get_container_status(s) if available else 'unknown'
        server_statuses.append({'server': s, 'docker_status': status})

    context = pa_context(request, {
        'docker_available': available,
        'system_info': system_info,
        'images': images,
        'server_statuses': server_statuses,
    })
    return render(request, 'platform_admin/docker/dashboard.html', context)


# ── Container Stats ──────────────────────────────────────────────────────────

@platform_admin_required
def pa_docker_stats(request, pk):
    """Container resource usage stats page."""
    server = get_object_or_404(PostgresServer, pk=pk, server_type='docker')
    docker_service = DockerService()

    stats = docker_service.get_container_stats(server)
    uptime = docker_service.get_container_uptime_info(server)
    processes = docker_service.get_container_processes(server)

    context = pa_context(request, {
        'server': server,
        'stats': stats,
        'uptime': uptime,
        'processes': processes,
    })
    return render(request, 'platform_admin/docker/stats.html', context)


@platform_admin_required
def pa_docker_stats_api(request, pk):
    """AJAX endpoint for live container stats (JSON)."""
    server = get_object_or_404(PostgresServer, pk=pk, server_type='docker')
    docker_service = DockerService()
    stats = docker_service.get_container_stats(server)
    return JsonResponse({'stats': stats or {}})


# ── Container Inspection ─────────────────────────────────────────────────────

@platform_admin_required
def pa_docker_inspect(request, pk):
    """Full container inspection details."""
    server = get_object_or_404(PostgresServer, pk=pk, server_type='docker')
    docker_service = DockerService()

    env_vars = docker_service.get_container_env(server)
    ports = docker_service.get_container_port_mappings(server)
    mounts = docker_service.get_container_mounts(server)
    networks = docker_service.get_container_network_info(server)
    uptime = docker_service.get_container_uptime_info(server)
    volume_info = docker_service.get_volume_info(server.docker_volume_name) if server.docker_volume_name else None

    context = pa_context(request, {
        'server': server,
        'env_vars': env_vars,
        'ports': ports,
        'mounts': mounts,
        'networks': networks,
        'uptime': uptime,
        'volume_info': volume_info,
    })
    return render(request, 'platform_admin/docker/inspect.html', context)


# ── Container Logs ───────────────────────────────────────────────────────────

@platform_admin_required
def pa_docker_logs(request, pk):
    """View container logs with configurable tail lines."""
    server = get_object_or_404(PostgresServer, pk=pk, server_type='docker')
    docker_service = DockerService()

    lines = int(request.GET.get('lines', 200))
    lines = min(lines, 5000)  # cap at 5000

    logs = docker_service.get_container_logs(server, lines=lines)

    context = pa_context(request, {
        'server': server,
        'logs': logs,
        'lines': lines,
    })
    return render(request, 'platform_admin/docker/logs.html', context)


# ── Container Actions ────────────────────────────────────────────────────────

@platform_admin_required
@require_POST
def pa_docker_restart(request, pk):
    """Restart a Docker container."""
    server = get_object_or_404(PostgresServer, pk=pk, server_type='docker')
    docker_service = DockerService()

    try:
        success = docker_service.restart_container(server)
        if success:
            messages.success(request, _('Container restarted successfully.'))
        else:
            messages.error(request, _('Failed to restart container.'))
    except Exception as e:
        messages.error(request, _(f'Error restarting container: {e}'))

    return redirect('tenants:pa_docker_stats', pk=pk)


@platform_admin_required
@require_POST
def pa_docker_resources(request, pk):
    """Update container resource limits."""
    server = get_object_or_404(PostgresServer, pk=pk, server_type='docker')
    docker_service = DockerService()

    memory = request.POST.get('memory_limit', '').strip() or None
    cpus = request.POST.get('cpus', '').strip() or None
    cpu_shares = request.POST.get('cpu_shares', '').strip() or None

    if cpu_shares:
        try:
            cpu_shares = int(cpu_shares)
        except ValueError:
            messages.error(request, _('CPU shares must be a number.'))
            return redirect('tenants:pa_docker_stats', pk=pk)

    try:
        success, output = docker_service.update_container_resources(
            server, memory_limit=memory, cpu_shares=cpu_shares, cpus=cpus
        )
        if success:
            messages.success(request, _('Resource limits updated successfully.'))
        else:
            messages.error(request, _(f'Failed to update resources: {output}'))
    except Exception as e:
        messages.error(request, _(f'Error updating resources: {e}'))

    return redirect('tenants:pa_docker_stats', pk=pk)


# ── Image Management ─────────────────────────────────────────────────────────

@platform_admin_required
@require_POST
def pa_docker_pull_image(request):
    """Pull a Docker image."""
    docker_service = DockerService()
    image_name = request.POST.get('image_name', '').strip()

    if not image_name:
        messages.error(request, _('Please provide an image name.'))
        return redirect('tenants:pa_docker_dashboard')

    # Safety: only allow postgres images
    if 'postgres' not in image_name.lower():
        messages.error(request, _('Only PostgreSQL images are allowed.'))
        return redirect('tenants:pa_docker_dashboard')

    try:
        success, output = docker_service.pull_image(image_name)
        if success:
            messages.success(request, _(f'Successfully pulled image: {image_name}'))
        else:
            messages.error(request, _(f'Failed to pull image: {output}'))
    except Exception as e:
        messages.error(request, _(f'Error pulling image: {e}'))

    return redirect('tenants:pa_docker_dashboard')


# ── Live Terminal ────────────────────────────────────────────────────────────

# Commands that are unsafe / destructive in a container context
BLOCKED_COMMANDS = [
    'rm -rf /', 'mkfs', 'dd if=', ':(){', 'fork bomb',
    'shutdown', 'reboot', 'halt', 'poweroff', 'init 0', 'init 6',
    '> /dev/sda', 'chmod -R 777 /', 'chown -R',
]

# Maximum output length to prevent browser hanging
MAX_OUTPUT_LENGTH = 100_000  # 100KB

# Command execution timeout in seconds
TERMINAL_TIMEOUT = 30


@platform_admin_required
def pa_docker_terminal(request, pk):
    """Live terminal page for Docker container."""
    server = get_object_or_404(PostgresServer, pk=pk, server_type='docker')
    docker_service = DockerService()
    container_status = docker_service.get_container_status(server)

    context = pa_context(request, {
        'server': server,
        'container_status': container_status,
    })
    return render(request, 'platform_admin/docker/terminal.html', context)


@platform_admin_required
@require_POST
def pa_docker_terminal_exec(request, pk):
    """
    AJAX endpoint: execute a command inside a Docker container.
    Returns JSON with stdout, stderr, exit_code, execution_time.
    """
    server = get_object_or_404(PostgresServer, pk=pk, server_type='docker')
    docker_service = DockerService()

    try:
        body = json.loads(request.body)
        command = body.get('command', '').strip()
    except (json.JSONDecodeError, AttributeError):
        command = request.POST.get('command', '').strip()

    if not command:
        return JsonResponse({'error': 'No command provided.'}, status=400)

    # Security: block dangerous commands
    cmd_lower = command.lower()
    for blocked in BLOCKED_COMMANDS:
        if blocked in cmd_lower:
            return JsonResponse({
                'error': f'Command blocked for safety: contains "{blocked}"',
                'blocked': True,
            }, status=403)

    # Check container is running
    status = docker_service.get_container_status(server)
    if status != 'running':
        return JsonResponse({
            'error': f'Container is not running (status: {status}).',
            'container_status': status,
        }, status=400)

    # Execute command with timeout
    import time
    import subprocess

    start_time = time.time()
    try:
        result = subprocess.run(
            ["docker", "exec", server.docker_container_name, "sh", "-c", command],
            capture_output=True,
            text=True,
            timeout=TERMINAL_TIMEOUT,
        )
        elapsed = round(time.time() - start_time, 3)

        stdout = result.stdout
        stderr = result.stderr

        # Truncate very large output
        truncated = False
        if len(stdout) > MAX_OUTPUT_LENGTH:
            stdout = stdout[:MAX_OUTPUT_LENGTH] + f'\n\n--- Output truncated at {MAX_OUTPUT_LENGTH // 1000}KB ---'
            truncated = True
        if len(stderr) > MAX_OUTPUT_LENGTH:
            stderr = stderr[:MAX_OUTPUT_LENGTH] + f'\n\n--- Output truncated at {MAX_OUTPUT_LENGTH // 1000}KB ---'
            truncated = True

        # Log the command execution
        ServerLog.objects.create(
            server=server,
            action='docker_container_update',
            message=f'Terminal exec: {command[:200]}',
            user=request.user,
        )

        return JsonResponse({
            'stdout': stdout,
            'stderr': stderr,
            'exit_code': result.returncode,
            'elapsed': elapsed,
            'truncated': truncated,
        })

    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - start_time, 3)
        return JsonResponse({
            'error': f'Command timed out after {TERMINAL_TIMEOUT}s.',
            'exit_code': -1,
            'elapsed': elapsed,
            'timeout': True,
        }, status=408)
    except Exception as e:
        return JsonResponse({
            'error': str(e),
            'exit_code': -1,
        }, status=500)