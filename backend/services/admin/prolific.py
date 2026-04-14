"""Prolific API client for automated study management.

All Prolific HTTP calls live here. The service is stateless -- it receives
the API token and base URL from config, and is only called when Prolific
integration is enabled.
"""

from __future__ import annotations

import logging
import secrets
import string

import httpx

from config import ProlificMode, ProlificSettings

logger = logging.getLogger(__name__)

COMPLETION_CODE_LENGTH = 8
COMPLETION_URL_TEMPLATE = "https://app.prolific.com/submissions/complete?cc={code}"
REAL_STUDY_URL_TEMPLATE = "https://app.prolific.com/researcher/workspaces/studies/{study_id}"


def generate_completion_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(COMPLETION_CODE_LENGTH))


def build_completion_url(code: str) -> str:
    return COMPLETION_URL_TEMPLATE.format(code=code)


def build_external_study_url(*, site_url: str, experiment_id: int) -> str:
    return (
        f"{site_url}/rate"
        f"?experiment_id={experiment_id}"
        f"&PROLIFIC_PID={{{{%PROLIFIC_PID%}}}}"
        f"&STUDY_ID={{{{%STUDY_ID%}}}}"
        f"&SESSION_ID={{{{%SESSION_ID%}}}}"
    )


def build_study_url(*, study_id: str) -> str:
    return REAL_STUDY_URL_TEMPLATE.format(study_id=study_id)


def _build_client(settings: ProlificSettings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.base_url,
        headers={"Authorization": f"Token {settings.api_token}"},
        timeout=30.0,
    )


async def _transition_real_study(
    *,
    settings: ProlificSettings,
    study_id: str,
    action: str,
) -> dict:
    async with _build_client(settings) as client:
        response = await client.post(
            f"/studies/{study_id}/transition/",
            json={"action": action},
        )
        response.raise_for_status()
        return response.json()


async def create_study(
    *,
    settings: ProlificSettings,
    name: str,
    description: str,
    external_study_url: str,
    estimated_completion_time: int,
    reward: int,
    total_available_places: int,
    completion_code: str,
    device_compatibility: list[str] | None = None,
) -> dict[str, str]:
    if settings.mode != ProlificMode.REAL:
        raise RuntimeError("create_study called while Prolific mode is disabled")

    payload: dict = {
        "name": name,
        "description": description,
        "external_study_url": external_study_url,
        "estimated_completion_time": estimated_completion_time,
        "reward": reward,
        "total_available_places": total_available_places,
        "prolific_id_option": "url_parameters",
        "device_compatibility": device_compatibility or ["desktop"],
        "completion_codes": [
            {
                "code": completion_code,
                "code_type": "COMPLETED",
                "actions": [{"action": "AUTOMATICALLY_APPROVE"}],
            }
        ],
    }

    async with _build_client(settings) as client:
        response = await client.post("/studies/", json=payload)
        response.raise_for_status()
        return response.json()


async def publish_study(
    *,
    settings: ProlificSettings,
    study_id: str,
) -> dict[str, str]:
    if settings.mode != ProlificMode.REAL:
        raise RuntimeError("publish_study called while Prolific mode is disabled")

    return await _transition_real_study(
        settings=settings,
        study_id=study_id,
        action="PUBLISH",
    )


async def stop_study(
    *,
    settings: ProlificSettings,
    study_id: str,
) -> dict[str, str]:
    if settings.mode != ProlificMode.REAL:
        raise RuntimeError("stop_study called while Prolific mode is disabled")

    return await _transition_real_study(
        settings=settings,
        study_id=study_id,
        action="STOP",
    )


async def delete_study(
    *,
    settings: ProlificSettings,
    study_id: str,
) -> None:
    if settings.mode != ProlificMode.REAL:
        raise RuntimeError("delete_study called while Prolific mode is disabled")

    async with _build_client(settings) as client:
        response = await client.delete(f"/studies/{study_id}/")
        if response.status_code == 404:
            logger.warning(
                "Prolific study already deleted (404)",
                extra={"attributes": {"study_id": study_id}},
            )
            return
        response.raise_for_status()


async def get_study(
    *,
    settings: ProlificSettings,
    study_id: str,
) -> dict[str, str]:
    if settings.mode != ProlificMode.REAL:
        raise RuntimeError("get_study called while Prolific mode is disabled")

    async with _build_client(settings) as client:
        response = await client.get(f"/studies/{study_id}/")
        response.raise_for_status()
        return response.json()
