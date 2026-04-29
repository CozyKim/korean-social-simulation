"""Streamlit 대시보드 — import만 검증 (실행은 별도)."""

import importlib

import pytest


def test_dashboard_module_imports():
    pytest.importorskip("streamlit")
    mod = importlib.import_module("korean_social_simulation.dashboard")
    assert hasattr(mod, "main")
