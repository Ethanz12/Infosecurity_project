"""
Home app initialization for ISPJ_Web_App.
Marks the 'home' folder as a Python package.
"""

# Point to AppConfig if you have one
default_app_config = 'apps.home.apps.HomeConfig'

# Optional: Import signals for models
# from . import signals

# Optional: Logging setup (for development/debugging)
import logging
logger = logging.getLogger(__name__)

# ------------------------------------------------------------
# Optional: Development helper (for scripts, not HTTP requests)
# ------------------------------------------------------------
from django.db import connection

def test_db_connection():
    """
    Check if MySQL connection works (development only).
    Returns True if successful, False otherwise.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            return result[0] == 1
    except Exception as e:
        logger.error(f"MySQL connection failed: {e}")
        return False
