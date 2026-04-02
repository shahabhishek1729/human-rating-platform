from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import get_settings  # noqa: E402
from main import create_app  # noqa: E402
from models import SESSION_DURATION_MINUTES  # noqa: E402


@pytest.fixture(scope="session")
def sync_engine():
    settings = get_settings()
    return create_engine(settings.sync_database_url, pool_pre_ping=True)


@pytest.fixture(autouse=True)
def reset_database(request, sync_engine):
    if "e2e/" not in request.node.nodeid:
        return

    with sync_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE TABLE experiment_rounds, ratings, raters, questions, uploads, experiments "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def backdate_rater_session(sync_engine):
    def _apply(rater_id: int) -> None:
        with sync_engine.begin() as conn:
            conn.execute(
                text("UPDATE raters SET session_start = :session_start WHERE id = :rater_id"),
                {
                    "session_start": datetime.now(UTC)
                    - timedelta(minutes=SESSION_DURATION_MINUTES + 1),
                    "rater_id": rater_id,
                },
            )

    return _apply


@pytest.fixture
def client():
    settings = get_settings()
    original_token = settings.prolific.api_token
    original_admin_auth = settings.admin_auth_enabled
    if not settings.prolific.api_token:
        settings.prolific.api_token = "test-token"
    settings.admin_auth_enabled = False
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    settings.prolific.api_token = original_token
    settings.admin_auth_enabled = original_admin_auth
