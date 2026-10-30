"""Environment endpoint for BenchLab.
Provides host specs, runtimes, database targets, quota settings, and sanitized configs.
Strictly ensures NO passwords or secrets are disclosed.
"""

import os
import platform
import shutil
import subprocess
from typing import Any, Dict
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings

router = APIRouter(tags=["Environment"])


class HostSpecs(BaseModel):
    os: str
    os_release: str
    architecture: str
    processor: str
    physical_cores: int | None
    logical_cores: int | None
    total_memory_gib: float | None
    available_memory_gib: float | None
    workspace_disk_free_gib: float | None


class DatabaseTargets(BaseModel):
    postgresql_target_version: str
    mongodb_target_version: str
    cpu_limit_quota: float
    memory_limit_quota: str


class EnvironmentResponse(BaseModel):
    project_name: str
    spec_version: str
    environment: str
    python_version: str
    node_version: str | None
    host: HostSpecs
    database_targets: DatabaseTargets
    config: Dict[str, Any]
    counts: Dict[str, Dict[str, int]] | None = None


def _get_node_version() -> str | None:
    try:
        res = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=2)
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


@router.get(
    "/environment",
    response_model=EnvironmentResponse,
    summary="Host environment, hardware quotas, runtime versions, and sanitized configs",
)
def get_environment() -> EnvironmentResponse:
    settings = get_settings()

    # Collect memory and CPU metrics via psutil if available
    try:
        import psutil
        physical_cores = psutil.cpu_count(logical=False)
        logical_cores = psutil.cpu_count(logical=True)
        vmem = psutil.virtual_memory()
        total_mem_gib = round(vmem.total / (1024 ** 3), 2)
        avail_mem_gib = round(vmem.available / (1024 ** 3), 2)
    except Exception:
        physical_cores = os.cpu_count()
        logical_cores = os.cpu_count()
        total_mem_gib = None
        avail_mem_gib = None

    # Disk usage for current drive
    try:
        total, used, free = shutil.disk_usage(os.getcwd())
        disk_free_gib = round(free / (1024 ** 3), 2)
    except Exception:
        disk_free_gib = None

    host_specs = HostSpecs(
        os=platform.system(),
        os_release=platform.version(),
        architecture=platform.machine(),
        processor=platform.processor() or "Unknown",
        physical_cores=physical_cores,
        logical_cores=logical_cores,
        total_memory_gib=total_mem_gib,
        available_memory_gib=avail_mem_gib,
        workspace_disk_free_gib=disk_free_gib,
    )

    db_targets = DatabaseTargets(
        postgresql_target_version="17.2-alpine",
        mongodb_target_version="8.0.4",
        cpu_limit_quota=settings.container_cpu_limit,
        memory_limit_quota=settings.container_mem_limit,
    )

    # Collect live database record counts if available
    try:
        from app.api.datasets import _get_live_counts
        counts = _get_live_counts()
    except Exception:
        counts = None

    return EnvironmentResponse(
        project_name=settings.project_name,
        spec_version=settings.spec_version,
        environment=settings.environment,
        python_version=platform.python_version(),
        node_version=_get_node_version(),
        host=host_specs,
        database_targets=db_targets,
        config=settings.get_sanitized_config(),
        counts=counts,
    )
