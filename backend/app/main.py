"""Main FastAPI application for BenchLab.
Benchmark and evaluation platform for PostgreSQL vs MongoDB.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    settings = get_settings()
    yield
    # Shutdown actions (clean up resources if needed)


settings = get_settings()

app = FastAPI(
    title="BenchLab API",
    description="Evaluation and Benchmark Platform comparing PostgreSQL 17.2 vs MongoDB 8.0.4",
    version=settings.spec_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for Frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        f"http://localhost:{settings.frontend_port}",
        f"http://127.0.0.1:{settings.frontend_port}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(api_router)


@app.get("/", tags=["Root"])
def root():
    return {
        "project": "benchlab",
        "description": "PostgreSQL 17.2 vs MongoDB 8.0.4 Query Performance Benchmark",
        "spec_version": settings.spec_version,
        "docs": "/docs",
        "health": "/api/health",
        "environment": "/api/environment",
    }
