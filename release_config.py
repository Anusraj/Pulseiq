"""Runtime paths for the public Streamlit release."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent
PUBLIC_DATABASE = ROOT / "data" / "pulseiq_public.duckdb"
LOCAL_DATABASE = ROOT / "pulseiq.duckdb"
DATABASE = PUBLIC_DATABASE if PUBLIC_DATABASE.is_file() else LOCAL_DATABASE
