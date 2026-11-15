"""Shared fixtures. Synthetic data only."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.settings import load_settings
from app.main import create_app
from app.stt.providers import MockStt
from tests.test_api import NOTE, TODAY


@pytest.fixture
def env(tmp_path):
    """(TestClient, settings, mock STT) with a fixed 'today' and a temp data dir."""
    cfg = load_settings(tmp_path)
    cfg.today_override = TODAY
    stt = MockStt(NOTE)
    return TestClient(create_app(cfg, stt=stt, warm_stt=False)), cfg, stt
