import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.snowflake_conn import get_connection  # noqa: F401
