import os
import sys
from pathlib import Path


def pytest_configure():
    os.environ.setdefault("ENABLE_LLM_CONSTRAINT_EXTRACTION", "0")
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
