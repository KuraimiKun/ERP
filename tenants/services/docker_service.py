"""
Docker Service

Handles Docker container management for PostgreSQL servers.
Enterprise features: stats, resource limits, image management,
container inspection, restart, and environment configuration.
"""

import json
import subprocess
import logging
import time
import uuid
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class DockerService:
    """
    Service for managing Docker PostgreSQL containers.
    """
    
    def __init__(self):
        self.postgres_image = getattr(settings, 'DOCKER_POSTGRES_IMAGE', 'postgres:15-alpine')
        self.network_name = getattr(settings, 'DOCKER_NETWORK', 'erp_network')
    
    def _run_command(self, command, check=True):
        """
        Run a shell command and return the output.
        
        Args:
            command: Command string or list to execute
            check: Whether to raise exception on non-zero exit
            
        Returns:
            tuple: (success, output)
        """
        try:
            if isinstance(command, str):
                command = command.split()
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=check
            )
            return True, result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {e.stderr}")
            return False, e.stderr
        except Exception as e:
            logger.error(f"Error running command: {str(e)}")
            return False, str(e)
    
    def is_docker_available(self):
        """Check if Docker is available and running."""
        success, _ = self._run_command("docker info", check=False)
        return success
    
    def ensure_network_exists(self):
        """Create Docker network if it doesn't exist."""
        # Check if network exists
        success, output = self._run_command(
            f"docker network ls --filter name={self.network_name} -q",
            check=False
        )
        
        if success and output:
            return True  # Network exists
        
        # Create network
        success, output = self._run_command(
            f"docker network create {self.network_name}",
            check=False
        )
        
        if success:
            logger.info(f"Created Docker network: {self.network_name}")
            return True
        else:
            logger.warning(f"Could not create network: {output}")
            return False
    
    def pull_postgres_image(self):
        """Pull the PostgreSQL Docker image."""
        logger.info(f"Pulling PostgreSQL image: {self.postgres_image}")
        success, output = self._run_command(
            f"docker pull {self.postgres_image}",
            check=False
        )
        return success
    
    def create_postgres_container(
        self,
        name,
        description='',
        container_name=None,
        port=5432,
        postgres_password='postgres',
        max_databases=50,
        created_by=None
    ):
        """
        Create a new Docker PostgreSQL container.
        
        Args:
            name: Display name for the server
            description: Server description
            container_name: Docker container name (auto-generated if not provided)
            port: Host port to map
            postgres_password: PostgreSQL admin password
            max_databases: Maximum number of databases
            created_by: User who created the server
            
        Returns:
            PostgresServer: The created server instance
        """
        from ..models import PostgresServer, ServerLog
        
        if not self.is_docker_available():
            raise RuntimeError("Docker is not available or not running")
        
        # Ensure network exists
        self.ensure_network_exists()
        
        # Generate container name if not provided
        if not container_name:
            container_name = f"erp_postgres_{uuid.uuid4().hex[:8]}"
        
        # Volume name for persistent storage
        volume_name = f"{container_name}_data"
        
        # Create the container
        cmd = [
            "docker", "run", "-d",
            "--name", container_name,
            "--network", self.network_name,
            "-e", f"POSTGRES_PASSWORD={postgres_password}",
            "-p", f"{port}:5432",
            "-v", f"{volume_name}:/var/lib/postgresql/data",
            "--restart", "unless-stopped",
            self.postgres_image
        ]
        
        success, output = self._run_command(cmd, check=False)
        
        if not success:
            raise RuntimeError(f"Failed to create container: {output}")
        
        container_id = output[:12]  # Short container ID
        
        # Create the server record
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
            status='inactive',  # Will be active after health check
            created_by=created_by
        )
        
        # Log the creation
        ServerLog.objects.create(
            server=server,
            action='docker_container_create',
            level='success',
            message=f'Docker container {container_name} created successfully',
            user=created_by,
            details={
                'container_id': container_id,
                'port': port,
                'image': self.postgres_image
            }
        )
        
        # Wait for PostgreSQL to be ready
        logger.info(f"Waiting for PostgreSQL to be ready...")
        time.sleep(5)  # Give PostgreSQL time to start
        
        # Perform health check
        from .database_service import DatabaseService
        db_service = DatabaseService()
        
        for i in range(10):
            is_healthy, message = db_service.check_server_health(server)
            if is_healthy:
                logger.info(f"Server {name} is ready!")
                break
            time.sleep(2)
        
        return server
    
    def start_container(self, server):
        """
        Start a stopped Docker container.
        
        Args:
            server: PostgresServer instance
            
        Returns:
            bool: Success status
        """
        from ..models import ServerLog
        
        if not server.docker_container_name:
            raise ValueError("No Docker container name set for this server")
        
        success, output = self._run_command(
            f"docker start {server.docker_container_name}",
            check=False
        )
        
        if success:
            server.status = 'active'
            server.save()
            
            ServerLog.objects.create(
                server=server,
                action='docker_container_start',
                level='success',
                message=f'Container {server.docker_container_name} started'
            )
        else:
            ServerLog.objects.create(
                server=server,
                action='docker_container_start',
                level='error',
                message=f'Failed to start container: {output}'
            )
        
        return success
    
    def stop_container(self, server):
        """
        Stop a running Docker container.
        
        Args:
            server: PostgresServer instance
            
        Returns:
            bool: Success status
        """
        from ..models import ServerLog
        
        if not server.docker_container_name:
            raise ValueError("No Docker container name set for this server")
        
        success, output = self._run_command(
            f"docker stop {server.docker_container_name}",
            check=False
        )
        
        if success:
            server.status = 'inactive'
            server.save()
            
            ServerLog.objects.create(
                server=server,
                action='docker_container_stop',
                level='success',
                message=f'Container {server.docker_container_name} stopped'
            )
        else:
            ServerLog.objects.create(
                server=server,
                action='docker_container_stop',
                level='error',
                message=f'Failed to stop container: {output}'
            )
        
        return success
    
    def remove_container(self, server, remove_volume=False):
        """
        Remove a Docker container.
        
        Args:
            server: PostgresServer instance
            remove_volume: Whether to also remove the data volume
            
        Returns:
            bool: Success status
        """
        from ..models import ServerLog
        
        if not server.docker_container_name:
            raise ValueError("No Docker container name set for this server")
        
        # Stop container first
        self.stop_container(server)
        
        # Remove container
        success, output = self._run_command(
            f"docker rm {server.docker_container_name}",
            check=False
        )
        
        if not success:
            logger.warning(f"Failed to remove container: {output}")
        
        # Remove volume if requested
        if remove_volume and server.docker_volume_name:
            vol_success, vol_output = self._run_command(
                f"docker volume rm {server.docker_volume_name}",
                check=False
            )
            if not vol_success:
                logger.warning(f"Failed to remove volume: {vol_output}")
        
        ServerLog.objects.create(
            server=server,
            action='docker_container_remove',
            level='success' if success else 'warning',
            message=f'Container {server.docker_container_name} removed'
        )
        
        return success
    
    def get_container_status(self, server):
        """
        Get the status of a Docker container.
        
        Args:
            server: PostgresServer instance
            
        Returns:
            str: Container status or None if not found
        """
        if not server.docker_container_name:
            return None
        
        success, output = self._run_command(
            f"docker inspect --format={{{{.State.Status}}}} {server.docker_container_name}",
            check=False
        )
        
        return output if success else None
    
    def get_container_logs(self, server, lines=100):
        """
        Get recent logs from a Docker container.
        
        Args:
            server: PostgresServer instance
            lines: Number of log lines to retrieve
            
        Returns:
            str: Log output
        """
        if not server.docker_container_name:
            return ""
        
        success, output = self._run_command(
            f"docker logs --tail {lines} {server.docker_container_name}",
            check=False
        )
        
        return output if success else ""

    # ── Enterprise Features ───────────────────────────────────────────────

    def restart_container(self, server):
        """Restart a Docker container."""
        from ..models import ServerLog

        if not server.docker_container_name:
            raise ValueError("No Docker container name set for this server")

        success, output = self._run_command(
            f"docker restart {server.docker_container_name}",
            check=False,
        )

        ServerLog.objects.create(
            server=server,
            action='docker_container_restart',
            level='success' if success else 'error',
            message=f'Container restart {"succeeded" if success else "failed"}: {output}',
        )

        if success:
            server.status = 'active'
            server.save()

        return success

    def get_container_stats(self, server):
        """
        Get real-time resource usage stats for a Docker container.

        Returns dict with cpu_percent, memory_usage, memory_limit, memory_percent,
        net_io_in, net_io_out, block_read, block_write, pids.
        """
        if not server.docker_container_name:
            return None

        success, output = self._run_command(
            [
                "docker", "stats", server.docker_container_name,
                "--no-stream",
                "--format",
                '{"cpu":"{{.CPUPerc}}","mem_usage":"{{.MemUsage}}","mem_perc":"{{.MemPerc}}","net_io":"{{.NetIO}}","block_io":"{{.BlockIO}}","pids":"{{.PIDs}}"}',
            ],
            check=False,
        )

        if not success or not output:
            return None

        try:
            raw = json.loads(output.strip().split('\n')[0])

            # Parse memory usage "123.4MiB / 1GiB"
            mem_parts = raw.get('mem_usage', '0B / 0B').split(' / ')
            mem_used = mem_parts[0].strip() if len(mem_parts) > 0 else '0B'
            mem_limit = mem_parts[1].strip() if len(mem_parts) > 1 else '0B'

            # Parse net I/O "1.23kB / 4.56kB"
            net_parts = raw.get('net_io', '0B / 0B').split(' / ')
            net_in = net_parts[0].strip() if len(net_parts) > 0 else '0B'
            net_out = net_parts[1].strip() if len(net_parts) > 1 else '0B'

            # Parse block I/O
            blk_parts = raw.get('block_io', '0B / 0B').split(' / ')
            blk_read = blk_parts[0].strip() if len(blk_parts) > 0 else '0B'
            blk_write = blk_parts[1].strip() if len(blk_parts) > 1 else '0B'

            return {
                'cpu_percent': raw.get('cpu', '0%').rstrip('%'),
                'memory_used': mem_used,
                'memory_limit': mem_limit,
                'memory_percent': raw.get('mem_perc', '0%').rstrip('%'),
                'net_io_in': net_in,
                'net_io_out': net_out,
                'block_read': blk_read,
                'block_write': blk_write,
                'pids': raw.get('pids', '0'),
            }
        except (json.JSONDecodeError, IndexError, KeyError):
            return None

    def inspect_container(self, server):
        """
        Return the full `docker inspect` JSON for a container.
        """
        if not server.docker_container_name:
            return None

        success, output = self._run_command(
            ["docker", "inspect", server.docker_container_name],
            check=False,
        )

        if not success or not output:
            return None

        try:
            data = json.loads(output)
            return data[0] if isinstance(data, list) and data else data
        except json.JSONDecodeError:
            return None

    def get_container_processes(self, server):
        """
        List processes running inside the container (docker top).
        Returns list of dicts with UID, PID, PPID, CMD, etc.
        """
        if not server.docker_container_name:
            return []

        success, output = self._run_command(
            ["docker", "top", server.docker_container_name, "-eo", "pid,user,%cpu,%mem,vsz,rss,command"],
            check=False,
        )

        if not success or not output:
            return []

        lines = output.strip().split('\n')
        if len(lines) < 2:
            return []

        headers = [h.replace('%', 'pct_') for h in lines[0].lower().split()]
        processes = []
        for line in lines[1:]:
            parts = line.split(None, len(headers) - 1)
            if len(parts) >= len(headers):
                processes.append(dict(zip(headers, parts)))
        return processes

    def get_container_env(self, server):
        """
        Get environment variables from a running container.
        Returns list of {'key': ..., 'value': ...}.
        """
        if not server.docker_container_name:
            return []

        info = self.inspect_container(server)
        if not info:
            return []

        env_list = info.get('Config', {}).get('Env', [])
        result = []
        for entry in env_list:
            parts = entry.split('=', 1)
            key = parts[0]
            value = parts[1] if len(parts) > 1 else ''
            # Mask sensitive values
            if any(s in key.upper() for s in ('PASSWORD', 'SECRET', 'KEY', 'TOKEN')):
                value = '••••••••'
            result.append({'key': key, 'value': value})
        return result

    def get_container_port_mappings(self, server):
        """
        Get port mappings for a container.
        Returns list of {'container_port': ..., 'host_port': ..., 'host_ip': ...}.
        """
        if not server.docker_container_name:
            return []

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
                        'host_ip': b.get('HostIp', '0.0.0.0'),
                        'host_port': b.get('HostPort', ''),
                    })
            else:
                mappings.append({'container_port': container_port, 'host_ip': '', 'host_port': ''})
        return mappings

    def get_container_mounts(self, server):
        """
        Get volume mounts for a container.
        Returns list of dicts with type, source, destination, mode.
        """
        if not server.docker_container_name:
            return []

        info = self.inspect_container(server)
        if not info:
            return []

        mounts = info.get('Mounts', [])
        return [
            {
                'type': m.get('Type', ''),
                'source': m.get('Source', m.get('Name', '')),
                'destination': m.get('Destination', ''),
                'mode': m.get('Mode', 'rw'),
                'rw': m.get('RW', True),
            }
            for m in mounts
        ]

    def get_container_network_info(self, server):
        """
        Get network details for a container.
        """
        if not server.docker_container_name:
            return {}

        info = self.inspect_container(server)
        if not info:
            return {}

        nets = info.get('NetworkSettings', {}).get('Networks', {})
        result = {}
        for net_name, net_data in nets.items():
            result[net_name] = {
                'ip_address': net_data.get('IPAddress', ''),
                'gateway': net_data.get('Gateway', ''),
                'mac_address': net_data.get('MacAddress', ''),
                'network_id': net_data.get('NetworkID', '')[:12],
            }
        return result

    def get_container_uptime_info(self, server):
        """
        Get container creation time, start time, uptime details.
        Returns dict with created, started, status, uptime_seconds.
        """
        if not server.docker_container_name:
            return {}

        info = self.inspect_container(server)
        if not info:
            return {}

        state = info.get('State', {})
        return {
            'status': state.get('Status', 'unknown'),
            'running': state.get('Running', False),
            'started_at': state.get('StartedAt', ''),
            'finished_at': state.get('FinishedAt', ''),
            'restart_count': info.get('RestartCount', 0),
            'created': info.get('Created', ''),
            'image': info.get('Config', {}).get('Image', ''),
            'platform': info.get('Platform', ''),
        }

    def get_docker_images(self):
        """List available PostgreSQL-related Docker images."""
        success, output = self._run_command(
            ["docker", "images", "--format", '{"repo":"{{.Repository}}","tag":"{{.Tag}}","id":"{{.ID}}","size":"{{.Size}}","created":"{{.CreatedAt}}"}'],
            check=False,
        )

        if not success or not output:
            return []

        images = []
        for line in output.strip().split('\n'):
            try:
                img = json.loads(line)
                if 'postgres' in img.get('repo', '').lower():
                    images.append(img)
            except json.JSONDecodeError:
                continue
        return images

    def pull_image(self, image_name):
        """
        Pull a specific Docker image.
        Returns (success, output).
        """
        from ..models import ServerLog

        success, output = self._run_command(
            ["docker", "pull", image_name],
            check=False,
        )

        ServerLog.objects.create(
            action='docker_pull',
            level='success' if success else 'error',
            message=f'Pulled image {image_name}: {"OK" if success else output}',
            details={'image': image_name},
        )

        return success, output

    def get_docker_system_info(self):
        """
        Get Docker system-wide information (docker system df + info).
        Returns dict with images, containers, volumes, build_cache totals.
        """
        result = {
            'docker_version': '',
            'total_containers': 0,
            'running_containers': 0,
            'paused_containers': 0,
            'stopped_containers': 0,
            'total_images': 0,
            'storage_driver': '',
            'os': '',
            'architecture': '',
            'cpus': 0,
            'memory': '',
        }

        # Docker info
        success, output = self._run_command(
            ["docker", "info", "--format", '{"containers":{{.Containers}},"running":{{.ContainersRunning}},"paused":{{.ContainersPaused}},"stopped":{{.ContainersStopped}},"images":{{.Images}},"driver":"{{.Driver}}","os":"{{.OperatingSystem}}","arch":"{{.Architecture}}","cpus":{{.NCPU}},"memory":"{{.MemTotal}}"}'],
            check=False,
        )
        if success and output:
            try:
                info = json.loads(output.strip())
                result.update({
                    'total_containers': info.get('containers', 0),
                    'running_containers': info.get('running', 0),
                    'paused_containers': info.get('paused', 0),
                    'stopped_containers': info.get('stopped', 0),
                    'total_images': info.get('images', 0),
                    'storage_driver': info.get('driver', ''),
                    'os': info.get('os', ''),
                    'architecture': info.get('arch', ''),
                    'cpus': info.get('cpus', 0),
                    'memory': info.get('memory', ''),
                })
            except json.JSONDecodeError:
                pass

        # Docker version
        success, output = self._run_command(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            check=False,
        )
        if success and output:
            result['docker_version'] = output.strip()

        return result

    def update_container_resources(self, server, memory_limit=None, cpu_shares=None, cpus=None):
        """
        Update resource constraints on a running container.
        memory_limit: e.g. '512m', '1g'
        cpu_shares: relative weight (1024 = default)
        cpus: decimal CPU count e.g. '1.5'
        """
        from ..models import ServerLog

        if not server.docker_container_name:
            raise ValueError("No Docker container name set.")

        cmd = ["docker", "update"]
        details = {}

        if memory_limit:
            cmd.extend(["--memory", memory_limit])
            details['memory_limit'] = memory_limit
        if cpu_shares:
            cmd.extend(["--cpu-shares", str(cpu_shares)])
            details['cpu_shares'] = cpu_shares
        if cpus:
            cmd.extend(["--cpus", str(cpus)])
            details['cpus'] = cpus

        cmd.append(server.docker_container_name)
        success, output = self._run_command(cmd, check=False)

        ServerLog.objects.create(
            server=server,
            action='docker_container_update',
            level='success' if success else 'error',
            message=f'Resource update {"succeeded" if success else "failed"}: {output}',
            details=details,
        )

        return success, output

    def get_volume_info(self, volume_name):
        """
        Inspect a Docker volume.
        Returns dict with driver, mountpoint, labels, created.
        """
        if not volume_name:
            return None

        success, output = self._run_command(
            ["docker", "volume", "inspect", volume_name],
            check=False,
        )

        if not success or not output:
            return None

        try:
            data = json.loads(output)
            vol = data[0] if isinstance(data, list) and data else data
            return {
                'name': vol.get('Name', ''),
                'driver': vol.get('Driver', ''),
                'mountpoint': vol.get('Mountpoint', ''),
                'created': vol.get('CreatedAt', ''),
                'labels': vol.get('Labels', {}),
                'scope': vol.get('Scope', ''),
            }
        except json.JSONDecodeError:
            return None

    def exec_in_container(self, server, command):
        """
        Execute a command inside a container.
        Returns (success, output).
        """
        if not server.docker_container_name:
            raise ValueError("No Docker container name set.")

        cmd = ["docker", "exec", server.docker_container_name, "sh", "-c", command]
        return self._run_command(cmd, check=False)
