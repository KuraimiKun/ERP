"""
Docker Service

Handles Docker container management for PostgreSQL servers.
"""

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
