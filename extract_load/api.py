"""Phase 1 (Extract) - daily incremental pull from the CFPB complaints API.

For each day in [watermark - LOOKBACK_DAYS, today] it:
  1. asks the API how many complaints were received that day (hits.total),
  2. pulls that day's complaints as CSV (same columns as the bulk file),
  3. checks the row count matches,
  4. writes data/landing/api/date_received=YYYY-MM-DD.csv (overwritten -> idempotent).

Why CSV: the JSON search endpoint caps `size` at 10,000 and `format=json` 404s,
while `format=csv` returns every row for the date range in one response.

The lookback re-pulls recent days because companies update responses after filing.
Dedup/upsert on complaint_id happens at load time (see load_duckdb.py).

    python -m extract_load.api --start 2026-09-01           # first run / explicit range
    python -m extract_load.api                               # normal daily run (uses watermark)
    python -m extract_load.api --start 2026-09-01 --end 2026-09-07 --no-state
"""
import argparse
import csv
import datetime as dt
import io
import json
import logging
import time

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from extract_load.config import API_URL, LANDING_DIR, LOOKBACK_DAYS, STATE_FILE

log = logging.getLogger(__name__)
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "cfpb-complaints-analytics (portfolio project)"


@retry(stop=stop_after_attempt(5), wait=wait_exponential(min=2, max=60), reraise=True)
def _get(params: dict) -> requests.Response:
    r = SESSION.get(API_URL, params=params, timeout=300)
    r.raise_for_status()
    return r


def _day_params(day: dt.date) -> dict:
    # date_received_max is inclusive, so min == max selects exactly one day.
    return {
        "date_received_min": day.isoformat(),
        "date_received_max": day.isoformat(),
        "no_aggs": "true",
    }


def expected_count(day: dt.date) -> int:
    total = _get({**_day_params(day), "size": 0}).json()["hits"]["total"]
    return total["value"] if isinstance(total, dict) else int(total)


def fetch_day(day: dt.date) -> tuple[list[str], list[list[str]]]:
    """Return (header, rows) for complaints received on `day`."""
    expected = expected_count(day)
    if expected == 0:
        return [], []
    text = _get({**_day_params(day), "format": "csv"}).content.decode("utf-8-sig")
    header, *rows = csv.reader(io.StringIO(text))
    date_col = header.index("Date received")
    rows = [r for r in rows if r[date_col][:10] == day.isoformat()]
    if len(rows) != expected:
        log.warning("%s: expected %s rows, got %s", day, expected, len(rows))
    return header, rows


def write_day(day: dt.date, header: list[str], rows: list[list[str]]) -> None:
    out = LANDING_DIR / f"date_received={day.isoformat()}.csv"
    if not rows:
        out.unlink(missing_ok=True)
        log.info("%s: no complaints", day)
        return
    tmp = out.with_suffix(".csv.part")
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    tmp.replace(out)  # only a complete file gets the real name
    log.info("%s: wrote %s rows -> %s", day, len(rows), out.name)


def read_watermark() -> dt.date | None:
    if STATE_FILE.exists():
        return dt.date.fromisoformat(json.loads(STATE_FILE.read_text())["last_date_loaded"])
    return None


def save_watermark(day: dt.date) -> None:
    STATE_FILE.write_text(json.dumps({"last_date_loaded": day.isoformat()}, indent=2))


def run(start: dt.date, end: dt.date, update_state: bool = True) -> int:
    total = 0
    day = start
    while day <= end:
        header, rows = fetch_day(day)
        write_day(day, header, rows)
        total += len(rows)
        if update_state:
            save_watermark(day)  # advance only after a day is written successfully
        day += dt.timedelta(days=1)
        time.sleep(0.5)  # be polite to a free public API
    log.info("Done: %s rows for %s -> %s", total, start, end)
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--start", type=dt.date.fromisoformat, help="YYYY-MM-DD (overrides watermark)")
    ap.add_argument("--end", type=dt.date.fromisoformat, default=dt.date.today())
    ap.add_argument("--lookback", type=int, default=LOOKBACK_DAYS)
    ap.add_argument("--no-state", action="store_true", help="don't read/write the watermark")
    args = ap.parse_args()

    if args.start:
        start = args.start
    else:
        wm = None if args.no_state else read_watermark()
        if wm is None:
            ap.error("No watermark yet - pass --start YYYY-MM-DD (e.g. the day after the bulk file ends)")
        start = wm - dt.timedelta(days=args.lookback)

    run(start, args.end, update_state=not args.no_state)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
