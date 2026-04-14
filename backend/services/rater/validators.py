from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models import Rater
from .mappers import build_session_end_time

logger = logging.getLogger(__name__)


def validate_rating_confidence(confidence: int) -> None:
    if confidence < 1 or confidence > 5:
        raise HTTPException(status_code=400, detail="Confidence must be between 1 and 5")


def validate_question_belongs_to_rater_experiment(
    *,
    question_experiment_id: int,
    rater_experiment_id: int,
) -> None:
    if question_experiment_id != rater_experiment_id:
        raise HTTPException(status_code=400, detail="Question does not belong to this experiment")


def validate_existing_rater_can_resume(existing_rater: Rater) -> None:
    if datetime.now(UTC) > build_session_end_time(existing_rater.session_start):
        raise HTTPException(
            status_code=403,
            detail="You have already completed a session for this experiment",
        )
    if not existing_rater.is_active:
        raise HTTPException(
            status_code=403,
            detail="You have already completed a session for this experiment",
        )


async def validate_rater_session_is_active(rater: Rater, db: AsyncSession) -> None:
    if datetime.now(UTC) <= build_session_end_time(rater.session_start):
        return

    logger.warning(
        "Rater session expired",
        extra={
            "attributes": {
                "rater_id": rater.id,
                "experiment_id": rater.experiment_id,
            }
        },
    )
    rater.is_active = False
    rater.session_end = datetime.now(UTC)
    await db.commit()
    raise HTTPException(status_code=403, detail="Session expired")


def validate_rater_marked_active(rater: Rater) -> None:
    if not rater.is_active:
        raise HTTPException(status_code=403, detail="Session expired")
