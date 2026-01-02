import json
import logging
import os
import shlex
import subprocess
import uuid
from typing import Any

from pydantic import BaseModel


class DockerEnvironmentConfig(BaseModel):
    image: str
    cwd: str = "/"
    """Working directory in which to execute commands."""
    env: dict[str, str] = {}
    """Environment variables to set in the container."""
    forward_env: list[str] = []
    """Environment variables to forward to the container.
    Variables are only forwarded if they are set in the host environment.
    In case of conflict with `env`, the `env` variables take precedence.
    """
    timeout: int = 30
    """Timeout for executing commands in the container."""
    executable: str = os.getenv("MSWEA_DOCKER_EXECUTABLE", "docker")
    """Path to the docker/container executable."""
    run_args: list[str] = ["--rm"]
    """Additional arguments to pass to the docker/container executable.
    Default is ["--rm"], which removes the container after it exits.
    """
    container_timeout: str = "2h"
    """Max duration to keep container running. Uses the same format as the sleep command."""
    pull_timeout: int = 120
    """Timeout in seconds for pulling images."""


class DockerEnvironmentCam:
    def __init__(
            self,
            *,
            config_class: type = DockerEnvironmentConfig,
            logger: logging.Logger | None = None,
            **kwargs,
    ):
        """This class executes bash commands in a Docker container using direct docker commands.
        See `DockerEnvironmentConfig` for keyword arguments.
        """
        self.logger = logger or logging.getLogger("minisweagent.environment")
        self.container_id: str | None = None
        self.config = config_class(**kwargs)

        # Set UTF-8 encoding environment variables to avoid ASCII errors
        utf8_env = {
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
        }
        # Merge with existing env, user-provided env takes precedence
        self.config.env = {**utf8_env, **self.config.env}

        self._start_container()

        # Setup pytest after container starts
        self._setup_pytest()

    def get_template_vars(self) -> dict[str, Any]:
        return self.config.model_dump()

    def _start_container(self):
        """Start the Docker container and return the container ID."""
        container_name = f"minisweagent-{uuid.uuid4().hex[:8]}"
        cmd = [
            self.config.executable,
            "run",
            "-d",
            "--name",
            container_name,
            "-w",
            self.config.cwd,
        ]

        # Add environment variables for UTF-8 encoding
        for key, value in self.config.env.items():
            cmd.extend(["-e", f"{key}={value}"])

        cmd.extend([
            *self.config.run_args,
            self.config.image,
            "sleep",
            self.config.container_timeout,
        ])

        self.logger.debug(f"Starting container with command: {shlex.join(cmd)}")
        self.logger.info(f"Container encoding set to UTF-8 (LANG=C.UTF-8, LC_ALL=C.UTF-8, PYTHONIOENCODING=utf-8)")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.config.pull_timeout,  # docker pull might take a while
            check=True,
        )
        self.logger.info(f"Started container {container_name} with ID {result.stdout.strip()}")
        self.container_id = result.stdout.strip()

    def _setup_pytest(self):
        """Check if pytest is installed and install it if necessary."""
        # Detect Python version and executable
        python_check = self.execute("command -v python3 && echo 'python3' || (command -v python && echo 'python')")
        if python_check["returncode"] != 0 or not python_check["output"].strip():
            self.logger.warning("Python not found in container, skipping pytest setup")
            return

        python_exe = python_check["output"].strip().split('\n')[-1]

        # Get Python version
        version_result = self.execute(f"{python_exe} --version")
        if version_result["returncode"] == 0:
            python_version = version_result["output"].strip()
            self.logger.info(f"Detected {python_version}")

        # Check if pytest is already installed
        pytest_check = self.execute(f"{python_exe} -m pytest --version 2>&1")

        if pytest_check["returncode"] == 0:
            pytest_info = pytest_check["output"].strip().split('\n')[0]
            self.logger.info(f"pytest already installed: {pytest_info}")
        else:
            self.logger.info("pytest not found, installing pytest...")

            # Install pytest with fallback for different Python versions
            install_cmd = f"{python_exe} -m pip install pytest --break-system-packages 2>&1 || {python_exe} -m pip install pytest 2>&1"
            install_result = self.execute(install_cmd, timeout=120)

            if install_result["returncode"] == 0:
                # Verify installation
                verify_result = self.execute(f"{python_exe} -m pytest --version 2>&1")
                if verify_result["returncode"] == 0:
                    pytest_info = verify_result["output"].strip().split('\n')[0]
                    self.logger.info(f"pytest installed successfully: {pytest_info}")
                else:
                    self.logger.warning("pytest installation completed but verification failed")
            else:
                self.logger.error(f"Failed to install pytest: {install_result['output']}")

    def execute(self, command: str, cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        """Execute a command in the Docker container and return the result as a dict."""
        cwd = cwd or self.config.cwd
        assert self.container_id, "Container not started"

        cmd = [self.config.executable, "exec", "-w", cwd]
        for key in self.config.forward_env:
            if (value := os.getenv(key)) is not None:
                cmd.extend(["-e", f"{key}={value}"])
        for key, value in self.config.env.items():
            cmd.extend(["-e", f"{key}={value}"])
        cmd.extend([self.container_id, "bash", "-lc", command])

        result = subprocess.run(
            cmd,
            text=True,
            timeout=timeout or self.config.timeout,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        try:
            parsed = json.loads(result.stdout.strip())

            if isinstance(parsed, dict) and 'output' in parsed and 'returncode' in parsed:
                return {
                    "output": parsed['output'],
                    "returncode": parsed['returncode']
                }
        except (json.JSONDecodeError, AttributeError):
            pass

        return {"output": result.stdout, "returncode": result.returncode}

    def cleanup(self):
        """Stop and remove the Docker container."""
        if getattr(self, "container_id", None) is not None:  # if init fails early, container_id might not be set
            cmd = f"(timeout 60 {self.config.executable} stop {self.container_id} || {self.config.executable} rm -f {self.container_id}) >/dev/null 2>&1 &"
            subprocess.Popen(cmd, shell=True)

    def __del__(self):
        """Cleanup container when object is destroyed."""
        self.cleanup()