"""Test fixtures for users tests — reuses root conftest."""

import os
import sys

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Import all fixtures from root conftest
from tests.conftest import *  # noqa: E402, F401, F403
