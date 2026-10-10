"""Column layout shared by the DuckDB and Snowflake loaders."""
import re

# CSV header -> column name, in file order. Both the bulk file and the API's
# format=csv export use these headers.
CSV_COLUMNS = [
    "Date received", "Product", "Sub-product", "Issue", "Sub-issue",
    "Company public response", "Company", "State", "ZIP code", "Tags",
    "Submitted via", "Date sent to company", "Company response to consumer",
    "Timely response?", "Complaint ID",
]


def _snake(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


COLUMNS = [_snake(c) for c in CSV_COLUMNS]

# SELECT list renaming CSV headers to COLUMNS (for DuckDB's read_csv)
RENAMED_SELECT = ", ".join(f'"{src}" AS {dst}' for src, dst in zip(CSV_COLUMNS, COLUMNS))


def check_header(duck, path) -> None:
    """Fail loudly if the CFPB ever adds, drops or reorders a column."""
    rows = duck.execute(
        "SELECT column_name FROM (DESCRIBE SELECT * FROM read_csv(?, header=true, all_varchar=true))",
        [str(path)],
    ).fetchall()
    header = [r[0] for r in rows]
    if header != CSV_COLUMNS:
        raise ValueError(f"{path.name}: unexpected columns {header}")
