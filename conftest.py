"""Pytest configuration to silence Streamlit ScriptRunContext warnings during test execution."""

import logging
import warnings
import pytest


def pytest_configure(config):
    """Silences streamlit ScriptRunContext warnings when running in bare test mode."""
    warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
    warnings.filterwarnings("ignore", category=UserWarning, module="streamlit.*")
    logging.getLogger("streamlit").setLevel(logging.ERROR)
    logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)
    logging.getLogger("streamlit.runtime.state.session_state").setLevel(logging.ERROR)
