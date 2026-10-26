"""Entry point for python -m benchlab."""

import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from backend.benchlab.cli import main

if __name__ == "__main__":
    sys.exit(main())
