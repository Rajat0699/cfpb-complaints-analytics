"""Phase 2 (Load) - load extracted CSVs into Snowflake CFPB.RAW.COMPLAINTS.

For each CSV (bulk file and/or API day files):
  1. DuckDB converts it to Parquet with snake_case columns (all VARCHAR). The
     5 GB bulk CSV becomes ~155 MB in ~3 s, so the upload is small and Snowflake
     can COPY the split files in parallel.
  2. PUT the Parquet files to @RAW.COMPLAINTS_STAGE/<file>/ and COPY them into a temp table.
  3. MERGE into RAW.COMPLAINTS on complaint_id (newer load wins, no duplicates).
  4. Record the load in RAW.LOAD_LOG and clear the stage.

Files whose modification time matches their last LOAD_LOG entry are skipped.
Objects and credentials come from snowflake/setup.sql and .env.

    python -m extract_load.load_snowflake            # bulk file + all API landing files
    python -m extract_load.load_snowflake bulk       # just data/raw/complaints.csv
    python -m extract_load.load_snowflake api        # just data/landing/api/*.csv
    python -m extract_load.load_snowflake --force    # reload even if unchanged
"""
import argparse
import datetime as dt
import logging
import os
import re
import tempfile
from pathlib import Path

import duckdb
import snowflake.connector

from extract_load.config import (
    LANDING_DIR,
    RAW_DIR,
    SNOWFLAKE,
    SNOWFLAKE_PASSWORD,
    SNOWFLAKE_PRIVATE_KEY_PASSPHRASE,
    SNOWFLAKE_PRIVATE_KEY_PATH,
)
from extract_load.schema import COLUMNS, RENAMED_SELECT, check_header

log = logging.getLogger(__name__)

BULK_FILE = RAW_DIR / "complaints.csv"
STAGE = "RAW.COMPLAINTS_STAGE"
META = ["_load_source", "_source_file"]


def connect():
    if not SNOWFLAKE["account"]:
        raise SystemExit("SNOWFLAKE_ACCOUNT is not set - fill in .env (see .env.example)")
    kw = dict(SNOWFLAKE)
    if SNOWFLAKE_PRIVATE_KEY_PATH:
        kw["private_key_file"] = os.path.expanduser(SNOWFLAKE_PRIVATE_KEY_PATH)
        if SNOWFLAKE_PRIVATE_KEY_PASSPHRASE:
            kw["private_key_file_pwd"] = SNOWFLAKE_PRIVATE_KEY_PASSPHRASE
    elif SNOWFLAKE_PASSWORD:
        kw["password"] = SNOWFLAKE_PASSWORD
    else:
        raise SystemExit("Set SNOWFLAKE_PRIVATE_KEY_PATH or SNOWFLAKE_PASSWORD in .env")
    return snowflake.connector.connect(**kw)


def _mtime(path: Path) -> str:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).isoformat()


def _already_loaded(cur, path: Path) -> bool:
    cur.execute(
        "SELECT COUNT(*) > 0 FROM RAW.LOAD_LOG WHERE source_file = %s AND file_mtime >= %s::TIMESTAMP_TZ",
        (path.name, _mtime(path)),
    )
    return cur.fetchone()[0]


def to_parquet(csv_path: Path, out_dir: Path, source: str) -> list[Path]:
    """CSV -> Parquet files of <=100 MB in out_dir, with metadata columns added."""
    duck = duckdb.connect()
    check_header(duck, csv_path)
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    duck.execute(
        f"""
        COPY (
            SELECT {RENAMED_SELECT}, {q(source)} AS _load_source, {q(csv_path.name)} AS _source_file
            FROM read_csv({q(csv_path)}, header=true, all_varchar=true)
        ) TO {q(out_dir)} (FORMAT parquet, COMPRESSION zstd, FILE_SIZE_BYTES '100MB')
        """
    )
    duck.close()
    return sorted(out_dir.glob("*.parquet"))


def load_file(conn, path: Path, source: str) -> int:
    prefix = re.sub(r"[^A-Za-z0-9_-]", "_", path.stem)
    stage_path = f"@{STAGE}/{prefix}/"
    cols = COLUMNS + META

    with tempfile.TemporaryDirectory() as tmp:
        files = to_parquet(path, Path(tmp) / "parquet", source)
        cur = conn.cursor()
        cur.execute(f"REMOVE {stage_path}")
        cur.execute(
            f"PUT 'file://{Path(tmp).as_posix()}/parquet/*.parquet' {stage_path} "
            "AUTO_COMPRESS = FALSE OVERWRITE = TRUE PARALLEL = 8"
        )
    log.info("%s: staged %s Parquet file(s)", path.name, len(files))

    cur.execute(
        "CREATE OR REPLACE TEMPORARY TABLE INCOMING ("
        + ", ".join(f"{c} VARCHAR" for c in cols)
        + ")"
    )
    cur.execute(
        f"""
        COPY INTO INCOMING ({", ".join(cols)})
        FROM (SELECT {", ".join(f"$1:{c}::VARCHAR" for c in cols)} FROM {stage_path})
        FILE_FORMAT = (FORMAT_NAME = 'RAW.PARQUET_FMT')
        """
    )
    cur.execute("SELECT COUNT(*) FROM INCOMING")
    n = cur.fetchone()[0]

    updates = ", ".join(f"{c} = s.{c}" for c in cols)
    cur.execute("BEGIN")
    try:
        cur.execute(
            f"""
            MERGE INTO RAW.COMPLAINTS t
            USING (
                SELECT * FROM INCOMING
                QUALIFY ROW_NUMBER() OVER (PARTITION BY complaint_id ORDER BY complaint_id) = 1
            ) s
            ON t.complaint_id = s.complaint_id
            WHEN MATCHED THEN UPDATE SET {updates}, _loaded_at = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT ({", ".join(cols)}, _loaded_at)
                VALUES ({", ".join(f"s.{c}" for c in cols)}, CURRENT_TIMESTAMP())
            """
        )
        inserted, updated = cur.fetchone()
        cur.execute(
            "INSERT INTO RAW.LOAD_LOG (source_file, load_source, file_mtime, rows_in_file, rows_inserted, rows_updated) "
            "SELECT %s, %s, %s::TIMESTAMP_TZ, %s, %s, %s",
            (path.name, source, _mtime(path), n, inserted, updated),
        )
        cur.execute("COMMIT")
    except Exception:
        cur.execute("ROLLBACK")
        raise
    finally:
        cur.execute(f"REMOVE {stage_path}")
    log.info("%s: %s rows -> %s inserted, %s updated", path.name, f"{n:,}", f"{inserted:,}", f"{updated:,}")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", nargs="?", choices=["all", "bulk", "api"], default="all")
    ap.add_argument("--force", action="store_true", help="reload files even if unchanged")
    args = ap.parse_args()

    files = []
    if args.source in ("all", "bulk"):
        if BULK_FILE.exists():
            files.append((BULK_FILE, "bulk"))
        else:
            log.warning("%s not found - run `python -m extract_load.bulk` first", BULK_FILE)
    if args.source in ("all", "api"):
        files += [(p, "api") for p in sorted(LANDING_DIR.glob("date_received=*.csv"))]

    conn = connect()
    try:
        cur = conn.cursor()
        for path, source in files:
            if not args.force and _already_loaded(cur, path):
                log.info("%s: unchanged since last load, skipping", path.name)
                continue
            load_file(conn, path, source)
        cur.execute("SELECT COUNT(*) FROM RAW.COMPLAINTS")
        log.info("RAW.COMPLAINTS now has %s rows", f"{cur.fetchone()[0]:,}")
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
