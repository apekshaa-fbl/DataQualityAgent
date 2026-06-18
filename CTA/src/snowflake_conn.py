"""
Snowflake connection helper.
Call get_connection(totp) once in run.py and pass conn through all stages.
Uses password + optional TOTP MFA (same as QMS shared connection).
"""
import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv(override=True)


def get_connection(totp: str = None):
    """Open and return a Snowflake connection (BI.DW)."""
    params = dict(
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database="BI",
        schema="DW",
    )
    totp = totp or os.getenv("SNOWFLAKE_TOTP")
    if totp:
        params["passcode"] = totp
    return snowflake.connector.connect(**params)
