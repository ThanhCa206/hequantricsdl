"""
scripts/setup_skeleton.py - Establish repository skeleton directories as specified in SPEC.md.
"""

from pathlib import Path

dirs_to_create = [
    "backend/app/api",
    "backend/app/domain",
    "backend/app/adapters",
    "backend/app/benchmark",
    "backend/app/datasets",
    "backend/app/reports",
    "frontend/src",
    "queries/postgresql",
    "queries/mongodb",
    "configs/profiles",
    "tests/unit",
    "tests/integration",
    "tests/correctness",
    "tests/e2e",
    "results",
]

for d in dirs_to_create:
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    if d.startswith("backend"):
        init_file = p / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Module initialization."""\n', encoding="utf-8")
    elif d.startswith("tests"):
        init_file = p / "__init__.py"
        if not init_file.exists():
            init_file.write_text('"""Test suite initialization."""\n', encoding="utf-8")
    else:
        gitkeep = p / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.write_text("", encoding="utf-8")

# Also ensure backend/app/__init__.py
app_init = Path("backend/app/__init__.py")
if not app_init.exists():
    app_init.write_text('"""BenchLab backend application."""\n', encoding="utf-8")

# Also ensure tests/__init__.py
tests_init = Path("tests/__init__.py")
if not tests_init.exists():
    tests_init.write_text('"""BenchLab test package."""\n', encoding="utf-8")

print("Skeleton directories initialized successfully.")
