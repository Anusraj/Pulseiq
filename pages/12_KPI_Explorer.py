"""Streamlit entry point for the Task 18 KPI explorer."""

from pathlib import Path
import runpy


runpy.run_path(
    str(Path(__file__).resolve().parents[1] / "phase4" / "task-18" / "kpi_explorer.py"),
    run_name="__main__",
)
