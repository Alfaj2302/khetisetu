"""Dev entry point for the KhetiSetu API.

Usage (after src/backend/.env is set up and sync.py/seed.py have been run):
    pip install -r src/backend/requirements.txt
    python src/backend/main.py
"""

from __future__ import annotations

from pathlib import Path

import uvicorn

from app.config import HOST, PORT

BACKEND_DIR = Path(__file__).resolve().parent

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        reload_dirs=[str(BACKEND_DIR)],
        app_dir=str(BACKEND_DIR),
    )
