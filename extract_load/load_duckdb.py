"""Phase 2 (Load, local) - load extracted CSVs into DuckDB at data/cfpb.duckdb.

Both sources share the same 15 CSV columns, so they land in one table:
  raw.complaints  - one row per complaint_id, all columns VARCHAR (typing happens in dbt)
  raw.load_log    - one row per file load

Each file is upserted on complaint_id (delete matching ids, then insert), so
reloading a file or re-pulling an API day never creates duplicates. Files whose
modification time matches their last load_log entry are skipped.

    python -m extract_load.load_duckdb            # bulk file + all API landing files
    python -m extract_load.load_duckdb bulk       # just data/raw/complaints.csv
    python -m extract_load.load_duckdb api        # just data/landing/api/*.csv
    python -m extract_load.load_duckdb --force    # reload even if unchanged
"""
import argparse
import datetime as dt
import logging
from pathlib import Path

import duckdb

from extract_load.config import DUCKDB_PATH, LANDING_DIR, RAW_DIR
from extract_load.schema import COLUMNS, RENAMED_SELECT, check_header

log = logging.getLogger(__name__)

BULK_FILE = RAW_DIR / "complaints.csv"

DDL = f"""
CREATE SCHEMA IF NOT EXISTS raw;
CREATE TABLE IF NOT EXISTS raw.complaints (
    {", ".join(f"{c} VARCHAR" for c in COLUMNS)},
    _load_source VARCHAR,
    _source_file VARCHAR,
    _loaded_at   TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS raw.load_log (
    source_file  VARCHAR,
    load_source  VARCHAR,
    file_mtime   TIMESTAMPTZ,
    rows_loaded  BIGINT,
    loaded_at    TIMESTAMPTZ
);
"""


def connect(path: Path = DUCKDB_PATH) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(path))
    con.execute(DDL)
    return con


def _mtime(path: Path) -> dt.datetime:
    return dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)


def _already_loaded(con, path: Path) -> bool:
    # compared in SQL: fetching TIMESTAMPTZ into Python would require pytz
    return con.execute(
        "SELECT count(*) > 0 FROM raw.load_log WHERE source_file = ? AND file_mtime >= ?",
        [str(path), _mtime(path)],
    ).fetchone()[0]


def load_file(con, path: Path, source: str) -> int:
    check_header(con, path)
    con.execute("BEGIN")
    try:
        con.execute(
            f"""
            CREATE OR REPLACE TEMP TABLE incoming AS
            SELECT {RENAMED_SELECT}, ? AS _load_source, ? AS _source_file, now() AS _loaded_at
            FROM read_csv(?, header=true, all_varchar=true)
            QUALIFY row_number() OVER (PARTITION BY "Complaint ID") = 1
            """,
            [source, path.name, str(path)],
        )
        n = con.execute("SELECT count(*) FROM incoming").fetchone()[0]
        con.execute("DELETE FROM raw.complaints WHERE complaint_id IN (SELECT complaint_id FROM incoming)")
        con.execute("INSERT INTO raw.complaints SELECT * FROM incoming")
        con.execute(
            "INSERT INTO raw.load_log VALUES (?, ?, ?, ?, now())",
            [str(path), source, _mtime(path), n],
        )
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    log.info("%s: upserted %s rows", path.name, f"{n:,}")
    return n


def load(con, files: list[tuple[Path, str]], force: bool = False) -> int:
    total = 0
    for path, source in files:
        if not force and _already_loaded(con, path):
            log.info("%s: unchanged since last load, skipping", path.name)
            continue
        total += load_file(con, path, source)
    return total


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

    con = connect()
    load(con, files, force=args.force)
    total = con.execute("SELECT count(*) FROM raw.complaints").fetchone()[0]
    log.info("raw.complaints now has %s rows (%s)", f"{total:,}", DUCKDB_PATH)
    con.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
