import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from shared.supabase_upsert import upsert_vetric_rows


def upsert_people_vetric_rows(rows):
    return upsert_vetric_rows(rows, profile_type="PERSON", label="people")
