"""Compatibility entry point for the complete local ETL pipeline."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from etl import main


if __name__ == "__main__":
    raise SystemExit(main())
