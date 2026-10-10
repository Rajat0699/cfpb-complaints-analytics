"""Shared settings and paths for the extract/load scripts."""
import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

API_URL = os.getenv(
    "CFPB_API_URL",
    "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/",
)
BULK_URL = os.getenv(
    "CFPB_BULK_URL", "https://files.consumerfinance.gov/ccdb/complaints.csv.zip"
)
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "30"))

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"               # bulk file lands here
LANDING_DIR = DATA_DIR / "landing" / "api"  # one JSONL file per day from the API
STATE_FILE = DATA_DIR / "state.json"     # watermark until Snowflake LOAD_LOG exists
DUCKDB_PATH = DATA_DIR / "cfpb.duckdb"   # local warehouse (before Snowflake)

for d in (RAW_DIR, LANDING_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Snowflake (see snowflake/setup.sql). Auth: key-pair if SNOWFLAKE_PRIVATE_KEY_PATH
# is set, otherwise SNOWFLAKE_PASSWORD (a programmatic access token also works there).
SNOWFLAKE = {
    "account": os.getenv("SNOWFLAKE_ACCOUNT"),
    "user": os.getenv("SNOWFLAKE_USER", "CFPB_LOADER_SVC"),
    "role": os.getenv("SNOWFLAKE_ROLE", "CFPB_LOADER"),
    "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "CFPB_WH"),
    "database": os.getenv("SNOWFLAKE_DATABASE", "CFPB"),
    "schema": os.getenv("SNOWFLAKE_SCHEMA", "RAW"),
}
SNOWFLAKE_PRIVATE_KEY_PATH = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE = os.getenv("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD")
