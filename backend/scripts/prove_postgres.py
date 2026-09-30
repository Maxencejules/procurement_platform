"""Run the real database proof; never silently substitute SQLite or skip it."""
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        raise SystemExit("Set TEST_DATABASE_URL to a disposable postgresql+asyncpg database")
    url = make_url(value)
    if url.drivername != "postgresql+asyncpg":
        raise SystemExit("TEST_DATABASE_URL must use postgresql+asyncpg")
    engine = create_engine(url.set(drivername="postgresql+psycopg2"))
    try:
        with engine.connect() as connection:
            print("Database proof:", connection.scalar(text("SELECT version()")), flush=True)
    finally:
        engine.dispose()
    backend = Path(__file__).resolve().parents[1]
    return subprocess.call([sys.executable, "-m", "pytest", "tests/postgres", "-v", "--tb=short"], cwd=backend)


if __name__ == "__main__":
    raise SystemExit(main())
