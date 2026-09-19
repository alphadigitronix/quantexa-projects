"""Thin wrapper redirecting to root dashboard.py (canonical single source of truth).

This prevents divergence and duplicate maintenance. All dashboard logic,
pages, state, and UI components reside strictly in dashboard.py at the project root.
"""
import os
import runpy

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROOT_DASHBOARD = os.path.join(_ROOT_DIR, "dashboard.py")

if __name__ == "__main__":
    runpy.run_path(_ROOT_DASHBOARD, run_name="__main__")
