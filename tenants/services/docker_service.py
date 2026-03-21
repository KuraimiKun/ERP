"""
Docker Service

Handles Docker container management for PostgreSQL servers.
Enterprise features: stats, resource limits, image management,
container inspection, restart, and environment configuration.

Security note
─────────────
This module uses the Python Docker SDK (``import docker``), which connects to the
Docker daemon via ``DOCKER_HOST`` from the environment.  In production the app is
configured to connect to a ``tecnativa/docker-socket-proxy`` sidecar running on
``tcp://127.0.0.1:2375`` instead of the raw ``/var/run/docker.sock``.  The proxy
exposes only the container/image/network/volume endpoints — the web process never
has a path to the raw socket, limiting blast radius if the app is compromised.
"""

import logging
import re
import time
import uuid

import docker
import docker.errors
from django.conf import settings

logger = logging.getLogger(__name__)

_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$')


def _validate_name(value, label='name'):
    """Reject names with shell metacharacters or path separators."""
    if not value or not _SAFE_NAME_RE.match(value):
        raise ValueError(
            f'Invalid {label}: {value!r}. '
            f'Only alphanumerics, hyphens, underscores, and dots are allowed.'
        )


def _bytes_to_human(n):
    """Convert byte count to a human-readable string (e.g. '123.4MiB')."""
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if n < 1024:
            return f'{n:.1f}{unit}'
        n /= 1024
    return f'{n:.1f}PiB'


class DockerService:
    """
    Service for managing Docker PostgreSQL containers via the Python SDK.

    Connects to the Docker daemon through ``DOCKER_HOST`` (environment variable)
    so the connection target can be overridden to a socket proxy without code
    changes.
    """

    def __init__(self):
        self.postgres_image = getattr(settings, 'DOCKER_POSTGRES_IMAGE', 'postgres:15-alpine')
        self.network_name   = getattr(settings, 'DOCKER_NETWORK', 'erp_network')

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _client(self):
        """
        Return a Docker SDK client.

        Reads ``DOCKER_HOST`` from the environment (set via .env / docker-compose).
        Falls back to the local socket when ``DOCKER_HOST`` is not set.
        """
        return docker.from_env()

    def _get_container(self, client, name):
        """Return the container object or raise docker.errors.NotFound."""
        _validate_name(name, 'container name')
        return client.containers.get(name)

    # ── Health / availability ─────────────────────────────────────────────────

    def is_docker_available(self):
        """Return True if the Docker daemon (or proxy) is reachable."""
        try:
            self._client().ping()
            return True
        except Exception:
            return False

    # ── Network ───────────────────────────────────────────────────────────────

    def ensure_network_exists(self):
        """Create the ERP Docker network if it does not already exist."""
        _validate_name(self.network_name, 'network name')
        client = self._client()
        try:
            existing = client.networks.list(names=[self.network_name])
            # names filter is a substring match; verify exact match
            if any(n.name == self.network_name for n in existing):
                return True
            client.networks.create(self.network_name, driver='bridge')
            logger.info('Created Docker network: %s', self.network_name)
            return True
        except docker.errors.APIError as exc:
            logger.warning('Could not create network %s: %s', self.network_name, exc)
            return False

    # ── Image management ──────────────────────────────────────────────────────

    def pull_postgres_image(self):
        """Pull (or refresh) the configured PostgreSQL image."""
        logger.info('Pulling PostgreSQL image: %s', self.postgres_image)
        try:
            self._client().images.pull(self.postgres_image)
            return True
        except docker.errors.APIError as exc:
            logger.error('Failed to pull image %s: %s', self.postgres_image, exc)
            return False

    def get_docker_images(self):
        """Return a list of locally available PostgreSQL-related images."""
        try:
            images = self._client().images.list()
            result = []
            for img in images:
                for tag in img.tags:
                    if 'postgres' in tag.lower():
                        repo, _, tag_name = tag.partition(':')
                        result.append({
                            'repo': repo,
                            'tag': tag_name or 'latest',
                            'id': img.short_id.replace('sha256:', ''),
                            'size': _bytes_to_human(img.attrs.get('Size', 0)),
                            'created': img.attrs.get('Created', ''),
                        })
            return result
        except docker.errors.APIError:
            return []

    def pull_image(self, image_name):
        """
        Pull a specific Docker image.
        Returns (success, message).
        """
        from ..models import ServerLog
        try:
            self._client().images.pull(image_name)
            ServerLog.objects.create(
                action='docker_pull',
                level='success',
                message=f'Pulled image {image_name}: OK',
                details={'image': image_name},
            )
            return True, 'OK'
        except docker.errors.APIError as exc:
            msg = str(exc)
            ServerLog.objects.create(
                action='docker_pull',
                level='error',
                message=f'Failed to pull image {image_name}: {msg}',
                details={'image': image_name},
            )
            return False, msg

    # ── Container lifecycle ───────────────────────────────────────────────────

    def create_postgres_container(
        self,
        name,
        description='',
        container_name=None,
        port=5432,
        postgres_password='postgres',
        max_databases=50,
        created_by=None,
    ):
        """
        Create a new Docker PostgreSQL container and register it in the DB.

        Returns the created PostgresServer instance.
        """
        from ..models import PostgresServer, ServerLog

        if not self.is_docker_available():
            raise RuntimeError('Docker is not available or not running')

        self.ensure_network_exists()

        if not container_name:
            container_name = f'erp_postgres_{uuid.uuid4().hex[:8]}'
        _validate_name(container_name, 'container name')

        volume_name = f'{container_name}_data'
        client = self._client()

        try:
            container = client.containers.run(
                self.postgres_image,
                name=container_name,
                detach=True,
                environment={'POSTGRES_PASSWORD': postgres_password},
                ports={'5432/tcp': port},
                volumes={volume_name: {'bind': '/var/lib/postgresql/data', 'mode': 'rw'}},
                network=self.network_name,
                restart_policy={'Name': 'unless-stopped'},
            )
        except docker.errors.APIError as exc:
            raise RuntimeError(f'Failed to create container: {exc}') from exc

        container_id = container.short_id

        server = PostgresServer.objects.create(
            name=name,
            description=description,
            server_type='docker',
            host='localhost',
            port=port,
            admin_username='postgres',
            admin_password=postgres_password,
            docker_container_id=container_id,
            docker_container_name=container_name,
            docker_volume_name=volume_name,
            max_databases=max_databases,
            status='inactive',
            created_by=created_by,
        )

        ServerLog.objects.create(
            server=server,
            action='docker_container_create',
            level='success',
            message=f'Docker container {container_name} created successfully',
            user=created_by,
            details={'container_id': container_id, 'port': port, 'image': self.postgres_image},
        )

        logger.info('Waiting for PostgreSQL to be ready…')
        time.sleep(5)

        from .database_service import DatabaseService
        db_service = DatabaseService()
        for _ in range(10):
            is_healthy, _ = db_service.check_server_health(server)
            if is_healthy:
                logger.info('Server %s is ready.', name)
                break
            time.sleep(2)

        return server

    def start_container(self, server):
        """Start a stopped Docker container. Returns True on success."""
        from ..models import ServerLog

        if not server.docker_container_name:
            raise ValueError('No Docker container name set for this server')

        client = self._client()
        try:
            self._get_container(client, server.docker_container_name).start()
            server.status = 'active'
            server.save()
            ServerLog.objects.create(
                server=server,
                action='docker_container_start',
                level='success',
                message=f'Container {server.docker_container_name} started',
            )
            return True
        except docker.errors.APIError as exc:
            ServerLog.objects.create(
                server=server,
                action='docker_container_start',
                level='error',
                message=f'Failed to start container: {exc}',
            )
            return False

    def stop_container(self, server):
        """Stop a running Docker container. Returns True on success."""
        from ..models import ServerLog

        if not server.docker_container_name:
            raise ValueError('No Docker container name set for this server')

        client = self._client()
        try:
            self._get_container(client, server.docker_container_name).stop()
            server.status = 'inactive'
            server.save()
            ServerLog.objects.create(
                server=server,
                action='docker_container_stop',
                level='success',
                message=f'Container {server.docker_container_name} stopped',
            )
            return True
        except docker.errors.APIError as exc:
            ServerLog.objects.create(
                server=server,
                action='docker_container_stop',
                level='error',
                message=f'Failed to stop container: {exc}',
            )
            return False

    def restart_container(self, server):
        """Restart a Docker container. Returns True on success."""
        from ..models import ServerLog

        if not server.docker_container_name:
            raise ValueError('No Docker container name set for this server')

        client = self._client()
        try:
            self._get_container(client, server.docker_container_name).restart()
            server.status = 'active'
            server.save()
            ServerLog.objects.create(
                server=server,
                action='docker_container_restart',
                level='success',
                message=f'Container {server.docker_container_name} restarted',
            )
            return True
        except docker.errors.APIError as exc:
            ServerLog.objects.create(
                server=server,
                action='docker_container_restart',
                level='error',
                message=f'Container restart failed: {exc}',
            )
            return False

    def remove_container(self, server, remove_volume=False):
        """Remove a Docker container (stops it first). Returns True on success."""
        from ..models import ServerLog

        if not server.docker_container_name:
            raise ValueError('No Docker container name set for this server')

        self.stop_container(server)

        client = self._client()
        success = True
        try:
            self._get_container(client, server.docker_container_name).remove()
        except docker.errors.NotFound:
            pass  # Already gone
        except docker.errors.APIError as exc:
            logger.warning('Failed to remove container: %s', exc)
            success = False

        if remove_volume and server.docker_volume_name:
            _validate_name(server.docker_volume_name, 'volume name')
            try:
                client.volumes.get(server.docker_volume_name).remove()
            except (docker.errors.NotFound, docker.errors.APIError) as exc:
                logger.warning('Failed to remove volume: %s', exc)

        ServerLog.objects.create(
            server=server,
            action='docker_container_remove',
            level='success' if success else 'warning',
            message=f'Container {server.docker_container_name} removed',
        )
        return success

    # ── Container inspection ──────────────────────────────────────────────────

    def get_container_status(self, server):
        """Return the container status string, or None if not found."""
        if not server.docker_container_name:
            return None
        try:
            c = self._get_container(self._client(), server.docker_container_name)
            c.reload()
            return c.status
        except (docker.errors.NotFound, docker.errors.APIError):
            return None

    def get_container_logs(self, server, lines=100):
        """Return the last *lines* log lines from a container."""
        if not server.docker_container_name:
            return ''
        try:
            c = self._get_container(self._client(), server.docker_container_name)
            raw = c.logs(tail=int(lines), stdout=True, stderr=True)
            return raw.decode('utf-8', errors='replace') if isinstance(raw, bytes) else raw
        except (docker.errors.NotFound, docker.errors.APIError):
            return ''

    def inspect_container(self, server):
        """Return the full inspect dict for a container, or None."""
        if not server.docker_container_name:
            return None
        try:
            c = self._get_container(self._client(), server.docker_container_name)
            c.reload()
            return c.attrs
        except (docker.errors.NotFound, docker.errors.APIError):
            return None

    def get_container_stats(self, server):
        """
        Return real-time resource usage stats for a container.

        Returns a dict with cpu_percent, memory_used, memory_limit,
        memory_percent, net_io_in, net_io_out, block_read, block_write, pids.
        """
        if not server.docker_container_name:
            return None
        try:
            c = self._get_container(self._client(), server.docker_container_name)
            raw = c.stats(stream=False)

            # ── CPU % ──
            cpu_delta    = raw['cpu_stats']['cpu_usage']['total_usage'] \
                         - raw['precpu_stats']['cpu_usage']['total_usage']
            system_delta = raw['cpu_stats'].get('system_cpu_usage', 0) \
                         - raw['precpu_stats'].get('system_cpu_usage', 0)
            num_cpus     = raw['cpu_stats'].get('online_cpus') \
                        or len(raw['cpu_stats']['cpu_usage'].get('percpu_usage') or [1])
            cpu_pct = (cpu_delta / system_delta * num_cpus * 100.0) if system_delta else 0.0

            # ── Memory ──
            mem_stats  = raw.get('memory_stats', {})
            mem_used   = mem_stats.get('usage', 0)
            mem_limit  = mem_stats.get('limit', 0)
            mem_pct    = (mem_used / mem_limit * 100.0) if mem_limit else 0.0

            # ── Network I/O (sum across all interfaces) ──
            net_rx = net_tx = 0
            for iface in raw.get('networks', {}).values():
                net_rx += iface.get('rx_bytes', 0)
                net_tx += iface.get('tx_bytes', 0)

            # ── Block I/O ──
            blk_read = blk_write = 0
            for entry in raw.get('blkio_stats', {}).get('io_service_bytes_recursive') or []:
                if entry.get('op') == 'Read':
                    blk_read += entry.get('value', 0)
                elif entry.get('op') == 'Write':
                    blk_write += entry.get('value', 0)

            return {
                'cpu_percent':    f'{cpu_pct:.2f}',
                'memory_used':    _bytes_to_human(mem_used),
                'memory_limit':   _bytes_to_human(mem_limit),
                'memory_percent': f'{mem_pct:.2f}',
                'net_io_in':      _bytes_to_human(net_rx),
                'net_io_out':     _bytes_to_human(net_tx),
                'block_read':     _bytes_to_human(blk_read),
                'block_write':    _bytes_to_human(blk_write),
                'pids':           str(raw.get('pids_stats', {}).get('current', 0)),
            }
        except (docker.errors.NotFound, docker.errors.APIError, KeyError, ZeroDivisionError):
            return None

    def get_container_processes(self, server):
        """
        List processes inside the container.
        Returns a list of dicts with pid, user, pct_cpu, pct_mem, command, etc.
        """
        if not server.docker_container_name:
            return []
        try:
            c = self._get_container(self._client(), server.docker_container_name)
            result = c.top(ps_args='-eo pid,user,%cpu,%mem,vsz,rss,command')
            titles = [h.lower().replace('%', 'pct_') for h in result.get('Titles', [])]
            processes = []
            for row in result.get('Processes') or []:
                if len(row) >= len(titles):
                    processes.append(dict(zip(titles, row)))
            return processes
        except (docker.errors.NotFound, docker.errors.APIError):
            return []

    def get_container_env(self, server):
        """
        Return env vars from a running container.
        Sensitive values (PASSWORD, SECRET, KEY, TOKEN) are masked.
        """
        info = self.inspect_container(server)
        if not info:
            return []
        result = []
        for entry in info.get('Config', {}).get('Env') or []:
            key, _, value = entry.partition('=')
            if any(s in key.upper() for s in ('PASSWORD', 'SECRET', 'KEY', 'TOKEN')):
                value = '••••••••'
            result.append({'key': key, 'value': value})
        return result

    def get_container_port_mappings(self, server):
        """Return port mappings for a container."""
        info = self.inspect_container(server)
        if not info:
            return []
        ports_data = info.get('NetworkSettings', {}).get('Ports', {})
        mappings = []
        for container_port, bindings in ports_data.items():
            if bindings:
                for b in bindings:
                    mappings.append({
                        'container_port': container_port,
                        'host_ip':        b.get('HostIp', '127.0.0.1'),
                        'host_port':      b.get('HostPort', ''),
                    })
            else:
                mappings.append({'container_port': container_port, 'host_ip': '', 'host_port': ''})
        return mappings

    def get_container_mounts(self, server):
        """Return volume mounts for a container."""
        info = self.inspect_container(server)
        if not info:
            return []
        return [
            {
                'type':        m.get('Type', ''),
                'source':      m.get('Source', m.get('Name', '')),
                'destination': m.get('Destination', ''),
                'mode':        m.get('Mode', 'rw'),
                'rw':          m.get('RW', True),
            }
            for m in info.get('Mounts') or []
        ]

    def get_container_network_info(self, server):
        """Return network details for a container."""
        info = self.inspect_container(server)
        if not info:
            return {}
        result = {}
        for net_name, net_data in (info.get('NetworkSettings', {}).get('Networks') or {}).items():
            result[net_name] = {
                'ip_address': net_data.get('IPAddress', ''),
                'gateway':    net_data.get('Gateway', ''),
                'mac_address': net_data.get('MacAddress', ''),
                'network_id': net_data.get('NetworkID', '')[:12],
            }
        return result

    def get_container_uptime_info(self, server):
        """Return creation time, start time, and uptime details."""
        info = self.inspect_container(server)
        if not info:
            return {}
        state = info.get('State', {})
        return {
            'status':        state.get('Status', 'unknown'),
            'running':       state.get('Running', False),
            'started_at':    state.get('StartedAt', ''),
            'finished_at':   state.get('FinishedAt', ''),
            'restart_count': info.get('RestartCount', 0),
            'created':       info.get('Created', ''),
            'image':         info.get('Config', {}).get('Image', ''),
            'platform':      info.get('Platform', ''),
        }

    # ── Resource management ───────────────────────────────────────────────────

    def update_container_resources(self, server, memory_limit=None, cpu_shares=None, cpus=None):
        """
        Update resource constraints on a running container.

        memory_limit: e.g. '512m', '1g'
        cpu_shares:   relative weight (1024 = default)
        cpus:         decimal CPU count e.g. '1.5'
        """
        from ..models import ServerLog

        if not server.docker_container_name:
            raise ValueError('No Docker container name set.')

        update_kwargs = {}
        details = {}

        if memory_limit:
            # SDK accepts bytes; parse human strings like '512m', '1g'
            multipliers = {'k': 1024, 'm': 1024**2, 'g': 1024**3}
            raw = str(memory_limit).lower()
            suffix = raw[-1]
            try:
                if suffix in multipliers:
                    update_kwargs['mem_limit'] = int(float(raw[:-1]) * multipliers[suffix])
                else:
                    update_kwargs['mem_limit'] = int(raw)
                details['memory_limit'] = memory_limit
            except ValueError:
                pass

        if cpu_shares:
            update_kwargs['cpu_shares'] = int(cpu_shares)
            details['cpu_shares'] = cpu_shares

        if cpus:
            # SDK uses nano_cpus (1 CPU = 1_000_000_000 nano_cpus)
            update_kwargs['nano_cpus'] = int(float(cpus) * 1_000_000_000)
            details['cpus'] = cpus

        client = self._client()
        try:
            self._get_container(client, server.docker_container_name).update(**update_kwargs)
            success, msg = True, 'OK'
        except docker.errors.APIError as exc:
            success, msg = False, str(exc)

        ServerLog.objects.create(
            server=server,
            action='docker_container_update',
            level='success' if success else 'error',
            message=f'Resource update {"succeeded" if success else "failed"}: {msg}',
            details=details,
        )
        return success, msg

    # ── Volume inspection ─────────────────────────────────────────────────────

    def get_volume_info(self, volume_name):
        """Inspect a Docker volume. Returns a dict or None."""
        if not volume_name:
            return None
        try:
            vol = self._client().volumes.get(volume_name)
            return {
                'name':       vol.attrs.get('Name', ''),
                'driver':     vol.attrs.get('Driver', ''),
                'mountpoint': vol.attrs.get('Mountpoint', ''),
                'created':    vol.attrs.get('CreatedAt', ''),
                'labels':     vol.attrs.get('Labels') or {},
                'scope':      vol.attrs.get('Scope', ''),
            }
        except (docker.errors.NotFound, docker.errors.APIError):
            return None

    # ── System info ───────────────────────────────────────────────────────────

    def get_docker_system_info(self):
        """Return Docker system-wide information."""
        result = {
            'docker_version':     '',
            'total_containers':   0,
            'running_containers': 0,
            'paused_containers':  0,
            'stopped_containers': 0,
            'total_images':       0,
            'storage_driver':     '',
            'os':                 '',
            'architecture':       '',
            'cpus':               0,
            'memory':             '',
        }
        try:
            client = self._client()
            info = client.info()
            result.update({
                'total_containers':   info.get('Containers', 0),
                'running_containers': info.get('ContainersRunning', 0),
                'paused_containers':  info.get('ContainersPaused', 0),
                'stopped_containers': info.get('ContainersStopped', 0),
                'total_images':       info.get('Images', 0),
                'storage_driver':     info.get('Driver', ''),
                'os':                 info.get('OperatingSystem', ''),
                'architecture':       info.get('Architecture', ''),
                'cpus':               info.get('NCPU', 0),
                'memory':             _bytes_to_human(info.get('MemTotal', 0)),
            })
            version = client.version()
            result['docker_version'] = version.get('Version', '')
        except docker.errors.APIError:
            pass
        return result

    # ── Exec (whitelisted diagnostic commands only) ───────────────────────────

    # Commands allowed inside containers — read-only diagnostics only.
    _ALLOWED_EXEC_COMMANDS = {
        'pg_isready',
        'psql -l',
        'psql --version',
        'pg_controldata /var/lib/postgresql/data',
    }

    def exec_in_container(self, server, command):
        """
        Execute a **whitelisted** diagnostic command inside a container.
        Returns (success, output).

        Only commands listed in ``_ALLOWED_EXEC_COMMANDS`` are permitted.
        """
        if not server.docker_container_name:
            raise ValueError('No Docker container name set.')
        _validate_name(server.docker_container_name, 'container name')

        if command not in self._ALLOWED_EXEC_COMMANDS:
            raise ValueError(
                f'Command not allowed: {command!r}. '
                f'Permitted: {sorted(self._ALLOWED_EXEC_COMMANDS)}'
            )

        try:
            c = self._get_container(self._client(), server.docker_container_name)
            exit_code, output = c.exec_run(command.split())
            decoded = output.decode('utf-8', errors='replace') if output else ''
            return exit_code == 0, decoded
        except docker.errors.APIError as exc:
            return False, str(exc)
