"""Regenerate src/backend/openapi.json from the FastAPI app's schema.

Doesn't need a running server or a database connection — it only imports
the app object and reads its schema.

Usage:
    python src/backend/export_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app

OUTPUT_PATH = Path(__file__).resolve().parent / "openapi.json"

if __name__ == "__main__":
    OUTPUT_PATH.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"Wrote {OUTPUT_PATH}")
