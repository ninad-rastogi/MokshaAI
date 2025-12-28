"""
Moksha AI - Vedic Spiritual Guide Chatbot
Entry point for the application
"""

import sys
from pathlib import Path

from ui.main_app import main

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run main app
if __name__ == "__main__":
    main()
