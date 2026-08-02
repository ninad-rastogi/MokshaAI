"""Test fixtures for llm tests - reuses shared fixtures."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moksha.settings_test")

from tests.conftest import *  # noqa: E402, F401, F403
