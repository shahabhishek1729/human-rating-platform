from __future__ import annotations

import csv
import io
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import respx
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text

from config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _unique_name(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}"


PROLIFIC_BASE = get_settings().prolific.base_url
FAKE_STUDY_ID = "65abc123def456"


def _experiment_payload(name: str | None = None) -> dict:
    return {
        "name": name or _unique_name("experiment"),
        "num_ratings_per_question": 2,
        "prolific": {
            "description": "Test study",
            "estimated_completion_time": 10,
            "reward": 500,
            "total_available_places": 5,
        },
    }


def _create_experiment(client: TestClient) -> dict:
    """Create an experiment with mocked Prolific API.

    Must be called within an active ``respx.mock`` context.
    """
    _mock_create_study()
    response = client.post(
        "/api/admin/experiments",
        json=_experiment_payload(),
    )
    assert response.status_code == 200
    return response.json()


def _upload_questions(client: TestClient, experiment_id: int) -> None:
    csv_data = (
        "question_id,question_text,gt_answer,options,question_type\n"
        "q1,Is this useful?,Yes,Yes|No,MC\n"
        "q2,Explain why,,,"
    )
    response = client.post(
        f"/api/admin/experiments/{experiment_id}/upload",
        files={"file": ("questions.csv", csv_data, "text/csv")},
    )
    assert response.status_code == 200


def _start_session(client: TestClient, experiment_id: int, prolific_pid: str = "PID_A") -> dict:
    response = client.post(
        "/api/raters/start",
        params={
            "experiment_id": experiment_id,
            "PROLIFIC_PID": prolific_pid,
            "STUDY_ID": "STUDY_1",
            "SESSION_ID": f"SESSION_{prolific_pid}",
        },
    )
    assert response.status_code == 200
    return response.json()


def _seed_export_dataset(sync_engine, experiment_id: int, row_count: int) -> None:
    with sync_engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO questions (
                    experiment_id,
                    question_id,
                    question_text,
                    gt_answer,
                    options,
                    question_type,
                    extra_data
                )
                SELECT
                    :experiment_id,
                    CONCAT('bulk-', gs::text),
                    CONCAT('Bulk question ', gs::text),
                    '',
                    '',
                    'MC',
                    '{}'
                FROM generate_series(1, :row_count) AS gs
                """
            ),
            {"experiment_id": experiment_id, "row_count": row_count},
        )

        rater_id = conn.execute(
            text(
                """
                INSERT INTO raters (
                    prolific_id,
                    study_id,
                    session_id,
                    experiment_id,
                    session_start,
                    is_active
                )
                VALUES (
                    'PID_EXPORT',
                    'STUDY_EXPORT',
                    'SESSION_EXPORT',
                    :experiment_id,
                    NOW(),
                    true
                )
                RETURNING id
                """
            ),
            {"experiment_id": experiment_id},
        ).scalar_one()

        conn.execute(
            text(
                """
                INSERT INTO ratings (
                    question_id,
                    rater_id,
                    answer,
                    confidence,
                    time_started,
                    time_submitted
                )
                SELECT
                    q.id,
                    :rater_id,
                    'Yes',
                    3,
                    NOW(),
                    NOW()
                FROM questions q
                WHERE q.experiment_id = :experiment_id
                """
            ),
            {"experiment_id": experiment_id, "rater_id": rater_id},
        )


def test_health_endpoint_smoke(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert "version" in body
    assert "commit" in body


def test_list_experiments_returns_empty_list_initially(client: TestClient):
    response = client.get("/api/admin/experiments")
    assert response.status_code == 200
    assert response.json() == []


@respx.mock
def test_create_experiment_then_list_contains_it(client: TestClient):
    created = _create_experiment(client)

    response = client.get("/api/admin/experiments")
    assert response.status_code == 200
    items = response.json()

    assert len(items) == 1
    assert items[0]["id"] == created["id"]
    assert items[0]["question_count"] == 0
    assert items[0]["rating_count"] == 0


@respx.mock
def test_upload_questions_records_upload_and_stats(client: TestClient):
    experiment = _create_experiment(client)
    experiment_id = experiment["id"]

    _upload_questions(client, experiment_id)

    uploads_response = client.get(f"/api/admin/experiments/{experiment_id}/uploads")
    stats_response = client.get(f"/api/admin/experiments/{experiment_id}/stats")

    assert uploads_response.status_code == 200
    assert len(uploads_response.json()) == 1
    assert uploads_response.json()[0]["question_count"] == 2

    assert stats_response.status_code == 200
    stats_payload = stats_response.json()
    assert stats_payload["total_questions"] == 2
    assert stats_payload["total_ratings"] == 0


@respx.mock
def test_upload_rejects_non_csv_file(client: TestClient):
    experiment = _create_experiment(client)

    response = client.post(
        f"/api/admin/experiments/{experiment['id']}/upload",
        files={"file": ("questions.txt", "nope", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File must be a CSV file"


@respx.mock
def test_start_session_creates_new_rater_session(client: TestClient):
    experiment = _create_experiment(client)

    payload = _start_session(client, experiment["id"], prolific_pid="PID_1")

    assert payload["rater_id"] > 0
    assert payload["experiment_name"] == experiment["name"]
    assert payload["completion_url"] is not None


@respx.mock
def test_start_session_twice_resumes_same_active_session(client: TestClient):
    experiment = _create_experiment(client)

    first = _start_session(client, experiment["id"], prolific_pid="PID_RESUME")
    second = _start_session(client, experiment["id"], prolific_pid="PID_RESUME")

    assert first["rater_id"] == second["rater_id"]
    assert first["session_start"] == second["session_start"]


@respx.mock
def test_start_session_rejects_after_end_session(client: TestClient):
    experiment = _create_experiment(client)
    session_payload = _start_session(client, experiment["id"], prolific_pid="PID_DONE")

    end_response = client.post(
        "/api/raters/end-session",
        params={"rater_id": session_payload["rater_id"]},
    )
    restart_response = client.post(
        "/api/raters/start",
        params={
            "experiment_id": experiment["id"],
            "PROLIFIC_PID": "PID_DONE",
        },
    )

    assert end_response.status_code == 200
    assert restart_response.status_code == 403


@respx.mock
def test_next_question_returns_eligible_question(client: TestClient):
    experiment = _create_experiment(client)
    _upload_questions(client, experiment["id"])
    session_payload = _start_session(client, experiment["id"], prolific_pid="PID_NEXT")

    response = client.get(
        "/api/raters/next-question",
        params={"rater_id": session_payload["rater_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["question_id"] in {"q1", "q2"}


@respx.mock
def test_submit_rating_success_then_duplicate_rejected(client: TestClient):
    experiment = _create_experiment(client)
    _upload_questions(client, experiment["id"])
    session_payload = _start_session(client, experiment["id"], prolific_pid="PID_SUBMIT")

    question = client.get(
        "/api/raters/next-question",
        params={"rater_id": session_payload["rater_id"]},
    ).json()

    submit_payload = {
        "question_id": question["id"],
        "answer": "Yes",
        "confidence": 4,
        "time_started": datetime.now(UTC).isoformat(),
    }

    first = client.post(
        "/api/raters/submit",
        params={"rater_id": session_payload["rater_id"]},
        json=submit_payload,
    )
    duplicate = client.post(
        "/api/raters/submit",
        params={"rater_id": session_payload["rater_id"]},
        json=submit_payload,
    )

    assert first.status_code == 200
    assert first.json()["success"] is True
    assert duplicate.status_code == 400


@respx.mock
def test_submit_rating_rejects_invalid_confidence(client: TestClient):
    experiment = _create_experiment(client)
    _upload_questions(client, experiment["id"])
    session_payload = _start_session(client, experiment["id"], prolific_pid="PID_CONF")

    question = client.get(
        "/api/raters/next-question",
        params={"rater_id": session_payload["rater_id"]},
    ).json()

    response = client.post(
        "/api/raters/submit",
        params={"rater_id": session_payload["rater_id"]},
        json={
            "question_id": question["id"],
            "answer": "Yes",
            "confidence": 9,
            "time_started": datetime.now(UTC).isoformat(),
        },
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any(error["loc"][-1] == "confidence" for error in detail)


@respx.mock
def test_session_status_reflects_completed_questions(client: TestClient):
    experiment = _create_experiment(client)
    _upload_questions(client, experiment["id"])
    session_payload = _start_session(client, experiment["id"], prolific_pid="PID_STATUS")

    question = client.get(
        "/api/raters/next-question",
        params={"rater_id": session_payload["rater_id"]},
    ).json()
    client.post(
        "/api/raters/submit",
        params={"rater_id": session_payload["rater_id"]},
        json={
            "question_id": question["id"],
            "answer": "No",
            "confidence": 3,
            "time_started": datetime.now(UTC).isoformat(),
        },
    )

    response = client.get(
        "/api/raters/session-status",
        params={"rater_id": session_payload["rater_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["questions_completed"] == 1
    assert payload["time_remaining_seconds"] > 0


@respx.mock
def test_next_question_marks_expired_session_inactive(
    client: TestClient,
    backdate_rater_session,
):
    experiment = _create_experiment(client)
    _upload_questions(client, experiment["id"])
    session_payload = _start_session(client, experiment["id"], prolific_pid="PID_EXPIRED")

    backdate_rater_session(session_payload["rater_id"])

    expired_response = client.get(
        "/api/raters/next-question",
        params={"rater_id": session_payload["rater_id"]},
    )
    status_response = client.get(
        "/api/raters/session-status",
        params={"rater_id": session_payload["rater_id"]},
    )

    assert expired_response.status_code == 403
    assert expired_response.json()["detail"] == "Session expired"
    assert status_response.status_code == 200
    assert status_response.json()["is_active"] is False


@respx.mock
def test_export_ratings_streams_large_dataset_in_chunks(client: TestClient, sync_engine):
    settings = get_settings()
    row_count = settings.testing.export_seed_row_count
    experiment = _create_experiment(client)
    _seed_export_dataset(sync_engine, experiment["id"], row_count=row_count)

    with client.stream("GET", f"/api/admin/experiments/{experiment['id']}/export") as response:
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        chunks = list(response.iter_text())

    assert len(chunks) >= 1

    parsed_rows = list(csv.reader(io.StringIO("".join(chunks))))
    assert parsed_rows[0][0] == "rating_id"
    assert len(parsed_rows) == row_count + 1


@respx.mock
def test_analytics_endpoint_returns_expected_payload_shape(client: TestClient):
    experiment = _create_experiment(client)
    _upload_questions(client, experiment["id"])
    session_payload = _start_session(client, experiment["id"], prolific_pid="PID_ANALYTICS")

    question = client.get(
        "/api/raters/next-question",
        params={"rater_id": session_payload["rater_id"]},
    ).json()

    submit_response = client.post(
        "/api/raters/submit",
        params={"rater_id": session_payload["rater_id"]},
        json={
            "question_id": question["id"],
            "answer": "Yes",
            "confidence": 4,
            "time_started": datetime.now(UTC).isoformat(),
        },
    )
    assert submit_response.status_code == 200

    analytics_response = client.get(f"/api/admin/experiments/{experiment['id']}/analytics")
    assert analytics_response.status_code == 200

    payload = analytics_response.json()
    overview = payload["overview"]
    assert payload["experiment_name"] == experiment["name"]
    assert overview["total_questions"] == 2
    assert overview["total_ratings"] == 1
    assert overview["total_raters"] == 1
    assert isinstance(payload["questions"], list) and len(payload["questions"]) == 1
    assert isinstance(payload["raters"], list) and len(payload["raters"]) == 1
    assert payload["questions"][0]["answer_distribution"] == {"Yes": 1}


def test_migration_runner_current_and_history_commands_succeed():
    revision_ids = sorted(
        path.name.split("_")[0]
        for path in (BACKEND_DIR / "alembic" / "versions").glob("*.py")
        if path.name != "__init__.py"
    )
    assert revision_ids

    current = subprocess.run(
        ["sh", "scripts/migrate.sh", "current"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    history = subprocess.run(
        ["sh", "scripts/migrate.sh", "history"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )

    assert current.returncode == 0
    assert history.returncode == 0

    current_output = f"{current.stdout}\n{current.stderr}"
    history_output = f"{history.stdout}\n{history.stderr}"
    assert revision_ids[-1] in current_output
    for revision_id in revision_ids:
        assert revision_id in history_output


def test_app_creation_succeeds_with_default_env():
    env = os.environ.copy()
    env.setdefault("APP_SECRET_KEY", "test-secret")

    result = subprocess.run(
        [sys.executable, "-c", "from main import create_app; create_app(); print('ok')"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "ok" in result.stdout


# ── Prolific integration tests ──────────────────────────────────────────────
# These use respx to mock outbound httpx calls to the Prolific API, verifying
# the full path: TestClient → FastAPI → service → Prolific client → mock.


def _mock_create_study(*, status: int = 200) -> respx.Route:
    body = {"id": FAKE_STUDY_ID, "status": "UNPUBLISHED"} if status == 200 else {}
    return respx.post(f"{PROLIFIC_BASE}/studies/").mock(return_value=Response(status, json=body))


def _mock_publish_study() -> respx.Route:
    return respx.post(f"{PROLIFIC_BASE}/studies/{FAKE_STUDY_ID}/transition/").mock(
        return_value=Response(200, json={"id": FAKE_STUDY_ID, "status": "ACTIVE"})
    )


def _mock_delete_study(*, status: int = 204) -> respx.Route:
    body = {} if status == 204 else {"error": "fail"}
    return respx.delete(f"{PROLIFIC_BASE}/studies/{FAKE_STUDY_ID}/").mock(
        return_value=Response(status, json=body)
    )


@respx.mock
def test_prolific_create_stores_study_id(client: TestClient):
    data = _create_experiment(client)

    assert data["prolific_study_id"] == FAKE_STUDY_ID
    assert data["prolific_study_status"] == "UNPUBLISHED"
    assert data["prolific_study_url"] is not None
    assert FAKE_STUDY_ID in data["prolific_study_url"]
    assert data["prolific_completion_url"] is not None


@respx.mock
def test_prolific_create_failure_returns_502(client: TestClient):
    _mock_create_study(status=500)

    resp = client.post("/api/admin/experiments", json=_experiment_payload())

    assert resp.status_code == 502

    # Verify experiment was NOT persisted (rollback)
    experiments = client.get("/api/admin/experiments").json()
    assert len(experiments) == 0


@respx.mock
def test_prolific_publish_updates_status(client: TestClient):
    data = _create_experiment(client)
    experiment_id = data["id"]

    route = _mock_publish_study()

    resp = client.post(f"/api/admin/experiments/{experiment_id}/prolific/publish")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ACTIVE"
    assert route.called


@respx.mock
def test_prolific_delete_calls_prolific_api(client: TestClient):
    data = _create_experiment(client)
    experiment_id = data["id"]

    route = _mock_delete_study()

    resp = client.delete(f"/api/admin/experiments/{experiment_id}")

    assert resp.status_code == 200
    assert route.called

    experiments = client.get("/api/admin/experiments").json()
    assert all(e["id"] != experiment_id for e in experiments)


@respx.mock
def test_prolific_delete_succeeds_when_api_fails(client: TestClient):
    data = _create_experiment(client)
    experiment_id = data["id"]

    _mock_delete_study(status=500)

    resp = client.delete(f"/api/admin/experiments/{experiment_id}")

    # Local delete succeeds even when Prolific API fails
    assert resp.status_code == 200


@respx.mock
def test_prolific_delete_handles_404(client: TestClient):
    data = _create_experiment(client)
    experiment_id = data["id"]

    _mock_delete_study(status=404)

    resp = client.delete(f"/api/admin/experiments/{experiment_id}")

    assert resp.status_code == 200
