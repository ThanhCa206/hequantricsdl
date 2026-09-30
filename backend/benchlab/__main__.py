"""
backend/benchlab/__main__.py - Entry point when executed as a module: python -m benchlab
"""

import sys
from benchlab.cli import main

if __name__ == "__main__":
    sys.exit(main())
