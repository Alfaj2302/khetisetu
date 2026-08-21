"""One-time local setup script: creates the KhetiSetu schema (schema.sql)
and loads the seed data CSVs (/db at the repo root) into it, on whatever
Postgres instance DATABASE_URL points to.

Usage (after copying src/backend/.env.example to src/backend/.env and
filling in your local Postgres credentials):
    pip install -r src/backend/requirements.txt
    python src/backend/db/sync.py

Safe to re-run: skips schema creation if it's already applied, and skips
data loading if it's already loaded — each is checked independently.
"""

from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent.parent
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DATA_DIR = REPO_ROOT / "db"

load_dotenv(BACKEND_DIR / ".env")


def to_int(value: str) -> str:
    # pandas writes nullable-int columns as floats (e.g. "1.0"); Postgres
    # int columns reject that literal, so strip it back to a plain integer.
    return str(int(float(value)))


def fix_isoformat(value: str) -> str:
    # csv.writer would otherwise pass the "T" separator straight through;
    # Postgres accepts it, but normalizing keeps COPY input plain ISO SQL.
    return value.replace("T", " ")


# Load order matters: every table here must come after every table its
# foreign keys point at.
TABLE_SPECS = [
    {"table": "states", "csv": "states.csv"},
    {"table": "districts", "csv": "districts.csv"},
    {"table": "crops", "csv": "crops.csv"},
    {"table": "seasons", "csv": "seasons.csv"},
    {"table": "products", "csv": "products.csv", "drop": ["crop"]},
    {"table": "sources", "csv": "sources.csv"},
    {"table": "crop_calendar", "csv": "crop_calendar.csv"},
    {
        "table": "historical_sales",
        "csv": "historical_sales.csv",
        "transform": {"crop_id": to_int},
    },
    {"table": "crop_production", "csv": "crop_production.csv"},
    {
        "table": "crop_market_data",
        "csv": "crop_market_data.csv",
        "rename": {
            "expected_supply_qty_quintal": "expected_supply_qty",
            "expected_demand_qty_quintal": "expected_demand_qty",
        },
        # demand_gap is a GENERATED column — Postgres computes it, and an
        # explicit value in the INSERT/COPY column list would be rejected.
        "drop": ["demand_gap_quintal"],
    },
    {"table": "weather_history", "csv": "weather_history.csv"},
    {"table": "inventory", "csv": "inventory.csv"},
    {
        "table": "farmer_crop_intent",
        "csv": "farmer_crop_intent.csv",
        "transform": {"created_at": fix_isoformat},
    },
    {
        "table": "fertilizer_recommendations",
        "csv": "fertilizer_recommendations.csv",
        "drop": ["crop_name"],
    },
]


def apply_schema(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.states')")
        row = cur.fetchone()
        if row and row[0]:
            print("Schema already present (public.states exists) — skipping.")
            return

        print(f"Applying schema from {SCHEMA_PATH} ...")
        cur.execute(SCHEMA_PATH.read_text())
    conn.commit()
    print("Schema applied successfully.")


def load_csv(cur: psycopg.Cursor, spec: dict) -> int:
    csv_path = DATA_DIR / spec["csv"]
    drop = set(spec.get("drop", []))
    rename = spec.get("rename", {})
    transforms = spec.get("transform", {})

    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        src_cols = [c for c in (reader.fieldnames or []) if c not in drop]
        db_cols = [rename.get(c, c) for c in src_cols]

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        row_count = 0
        for row in reader:
            values = []
            for c in src_cols:
                value = row[c]
                transform = transforms.get(c)
                if transform and value != "":
                    value = transform(value)
                values.append(value)
            writer.writerow(values)
            row_count += 1

    column_list = ", ".join(db_cols)
    with cur.copy(f"COPY {spec['table']} ({column_list}) FROM STDIN WITH (FORMAT csv)") as copy:
        copy.write(buffer.getvalue())

    # CSVs carry explicit ids, which bypasses the id sequence — advance it
    # past the max loaded id so the app's own inserts don't collide.
    table = spec["table"]
    cur.execute(
        f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
        f"COALESCE((SELECT MAX(id) FROM {table}), 1))",
    )

    return row_count


def load_seed_data(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM states")
        row = cur.fetchone()
        if row and row[0]:
            print("Seed data already loaded (states has rows) — skipping.")
            return

        for spec in TABLE_SPECS:
            n = load_csv(cur, spec)
            print(f"  {spec['table']}: {n} rows")
    conn.commit()
    print("Seed data loaded successfully.")


def main() -> int:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print(
            "DATABASE_URL is not set. Copy src/backend/.env.example to "
            "src/backend/.env and fill in your Postgres credentials.",
            file=sys.stderr,
        )
        return 1

    with psycopg.connect(database_url) as conn:
        try:
            apply_schema(conn)
            load_seed_data(conn)
        except Exception as error:
            conn.rollback()
            print(f"Failed to sync database: {error}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
