"""API package initializing and combining routers."""

from fastapi import APIRouter
from app.api.datasets import router as datasets_router
from app.api.environment import router as environment_router
from app.api.health import router as health_router
from app.api.queries import router as queries_router
from app.api.benchmark import router as benchmark_router
from app.api.results import router as results_router
from app.api.tests_runner import router as tests_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(environment_router)
api_router.include_router(datasets_router)
api_router.include_router(queries_router)
api_router.include_router(benchmark_router)
api_router.include_router(results_router)
api_router.include_router(tests_router)

__all__ = ["api_router"]


