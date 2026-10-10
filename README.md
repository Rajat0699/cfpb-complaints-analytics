# CFPB Consumer Complaints Analytics

End-to-end ELT project on the CFPB Consumer Complaint Database (~18M complaints):
**CFPB API / bulk file → Python (+ DuckDB) → Snowflake (RAW) → dbt Cloud → marts → dashboard.**

## Project structure

| Folder | Phase | Status |
|---|---|---|
| `extract_load/` | 1–2 Extract & Load (Python) | `bulk.py`, `api.py`, `load_duckdb.py`, `load_snowflake.py` done |
| `snowflake/` | 0 Setup DDL (warehouse, roles, users, schemas, stage, raw tables) | done |
| `dbt/` | 3 Transform (staging → marts), run in dbt Cloud | staging + tests done; marts next |
| `.github/workflows/` | 4 Orchestration + CI | todo |
| `analysis/` | 5 Analytics notebooks / SQL | todo |
| `dashboard/` | 5 Dashboard | todo |
| `data/` | local landing zone (git-ignored) | — |

## Setup

```bash
./setup.sh                  # creates .venv, installs requirements, copies .env.example -> .env
source .venv/bin/activate
```

## Extract

```bash
# One-time backfill: full bulk file (~330 MB zip, ~5 GB CSV, ~18M rows) -> data/raw/
python -m extract_load.bulk

# Incremental API pull -> data/landing/api/date_received=YYYY-MM-DD.csv
python -m extract_load.api --start 2026-09-01   # first run
python -m extract_load.api                      # later runs: watermark minus 30-day lookback
```

`api.py` uses the API's `format=csv` export (same 15 columns as the bulk file; the JSON
endpoint caps results at 10,000 rows). `date_received_max` is inclusive, so each request
is one day. Each day's row count is checked against the API's `hits.total`.
Files are overwritten per day, so reruns are safe.

## Load (local DuckDB)

```bash
python -m extract_load.load_duckdb          # bulk file + all API files -> data/cfpb.duckdb
python -m extract_load.load_duckdb api      # only API files
```

- `raw.complaints`: one row per `complaint_id`, all VARCHAR, plus `_load_source` / `_source_file` / `_loaded_at`.
  Each file is upserted on `complaint_id`, so newer pulls replace older rows (no duplicates).
- `raw.load_log`: one row per file load; unchanged files are skipped (`--force` to reload).
- Note: bulk dates are `YYYY-MM-DD`, API dates are ISO timestamps; normalize in dbt staging.

## Snowflake (one-time setup)

1. In a Snowsight worksheet, as ACCOUNTADMIN, run [`snowflake/setup.sql`](snowflake/setup.sql).
2. Generate key pairs for the two service users and paste the printed `ALTER USER` statements into Snowsight:
   ```bash
   ./snowflake/make_keys.sh
   ```
3. In `.env`, set `SNOWFLAKE_ACCOUNT` (Snowsight > profile menu > *Connect a tool to Snowflake*).

## Load (Snowflake)

```bash
python -m extract_load.load_snowflake          # bulk file + all API files -> CFPB.RAW.COMPLAINTS
python -m extract_load.load_snowflake api      # only API files
```

Each CSV is converted to Parquet with DuckDB (the 5 GB bulk CSV becomes ~160 MB in seconds),
PUT to `@RAW.COMPLAINTS_STAGE`, COPYed into a temp table, then MERGEd into `RAW.COMPLAINTS`
on `complaint_id`. Every load is recorded in `RAW.LOAD_LOG` (rows inserted / updated).

## Transform (dbt Cloud)

The dbt project lives in [`dbt/`](dbt). In dbt Cloud: connect this GitHub repo, set the
**project subdirectory** to `dbt`, and use a Snowflake connection with user `CFPB_DBT_SVC`,
role `CFPB_TRANSFORMER`, warehouse `CFPB_WH`, database `CFPB`, key-pair auth
(`~/.snowflake/cfpb_dbt_key.p8`). Production schema: `ANALYTICS`.

- `stg_cfpb__complaints`: typed and cleaned complaints (dates parsed, `'None'` strings nulled, booleans).
- Tests: unique/not-null keys, accepted values, no future dates; `date_sent < date_received` warns (~7k source rows).
