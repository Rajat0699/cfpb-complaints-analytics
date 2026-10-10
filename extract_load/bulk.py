"""Phase 1 (Extract) - one-time backfill.

Downloads the full CFPB complaints bulk file and unzips it into data/raw/.

    python -m extract_load.bulk            # download + unzip
    python -m extract_load.bulk --no-unzip # keep only the zip
"""
import argparse
import logging
import zipfile
from pathlib import Path

import requests

from extract_load.config import BULK_URL, RAW_DIR

log = logging.getLogger(__name__)
CHUNK = 8 * 1024 * 1024  # 8 MB


def download(url: str = BULK_URL) -> Path:
    dest = RAW_DIR / url.rsplit("/", 1)[-1]
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("Downloading %s -> %s", url, dest)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(CHUNK):
                f.write(chunk)
                done += len(chunk)
                if total:
                    print(f"\r  {done / 1e6:,.0f} / {total / 1e6:,.0f} MB", end="", flush=True)
    print()
    tmp.replace(dest)  # only a finished download gets the real name
    return dest


def unzip(path) -> list:
    with zipfile.ZipFile(path) as z:
        z.extractall(RAW_DIR)
        names = z.namelist()
    log.info("Extracted: %s", names)
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-unzip", action="store_true")
    args = ap.parse_args()
    zpath = download()
    if not args.no_unzip:
        unzip(zpath)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    main()
