"""Business logic for the assistance endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models import AssistanceSession
from schemas import AssistanceStepResponse
from services.queries import (
    fetch_experiment_or_404,
    fetch_question_or_404,
    fetch_rater_or_404,
)

from .base import InteractionStep, StepType
from .registry import get_method

logger = logging.getLogger(__name__)


def _load_json(value: str | None) -> dict:
    return json.loads(value) if value else {}


async def _fetch_session_or_404(session_id: int, db: AsyncSession) -> AssistanceSession:
    session = (
        await db.execute(select(AssistanceSession).where(AssistanceSession.id == session_id))
    ).scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Assistance session not found")
    return session


def _apply_step_to_session(session: AssistanceSession, step: InteractionStep) -> None:
    session.step_type = step.type
    session.state = json.dumps(step.state) if step.state else None
    session.payload = json.dumps(step.payload) if step.payload else None
    session.is_complete = step.is_terminal
    session.updated_at = datetime.now(UTC)


def _step_to_response(session_id: int, step: InteractionStep) -> AssistanceStepResponse:
    return AssistanceStepResponse(
        session_id=session_id,
        type=step.type,
        payload=step.payload,
        is_terminal=step.is_terminal,
    )


async def _fetch_existing_session(
    rater_id: int, question_id: int, db: AsyncSession
) -> AssistanceSession | None:
    return (
        await db.execute(
            select(AssistanceSession).where(
                AssistanceSession.rater_id == rater_id,
                AssistanceSession.question_id == question_id,
            )
        )
    ).scalar_one_or_none()


async def start_assistance(
    *,
    rater_id: int,
    question_id: int,
    db: AsyncSession,
) -> AssistanceStepResponse:
    rater, question = await asyncio.gather(
        fetch_rater_or_404(rater_id, db),
        fetch_question_or_404(question_id, db),
    )
    if not rater.is_active:
        raise HTTPException(status_code=400, detail="Rater session is not active")

    if question.experiment_id != rater.experiment_id:
        raise HTTPException(
            status_code=400, detail="Question does not belong to rater's experiment"
        )

    existing = await _fetch_existing_session(rater_id, question_id, db)
    if existing:
        step = InteractionStep(
            type=StepType(existing.step_type),
            payload=_load_json(existing.payload),
            state=_load_json(existing.state),
            is_terminal=existing.is_complete,
        )
        return _step_to_response(existing.id, step)

    experiment = await fetch_experiment_or_404(rater.experiment_id, db)
    params = _load_json(experiment.assistance_params)

    try:
        method = get_method(experiment.assistance_method)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    step = await method.start(question, params)

    assistance_session = AssistanceSession(
        rater_id=rater_id,
        experiment_id=rater.experiment_id,
        question_id=question_id,
        method_name=experiment.assistance_method,
        params=json.dumps(params) if params else None,
        step_type=step.type,
        state=json.dumps(step.state) if step.state else None,
        payload=json.dumps(step.payload) if step.payload else None,
        is_complete=step.is_terminal,
    )
    db.add(assistance_session)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await _fetch_existing_session(rater_id, question_id, db)
        if existing:
            step = InteractionStep(
                type=StepType(existing.step_type),
                payload=_load_json(existing.payload),
                state=_load_json(existing.state),
                is_terminal=existing.is_complete,
            )
            return _step_to_response(existing.id, step)
        raise
    await db.refresh(assistance_session)

    logger.info(
        "Assistance started: session_id=%s, rater_id=%s, question_id=%s, method=%s",
        assistance_session.id,
        rater_id,
        question_id,
        experiment.assistance_method,
    )

    return _step_to_response(assistance_session.id, step)


async def advance_assistance(
    *,
    rater_id: int,
    session_id: int,
    human_input: str,
    db: AsyncSession,
) -> AssistanceStepResponse:
    assistance_session = await _fetch_session_or_404(session_id, db)

    if assistance_session.rater_id != rater_id:
        raise HTTPException(status_code=403, detail="Session does not belong to rater")

    if assistance_session.is_complete:
        raise HTTPException(status_code=400, detail="Assistance session is already complete")

    params = _load_json(assistance_session.params)
    state = _load_json(assistance_session.state)

    try:
        method = get_method(assistance_session.method_name)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    step = await method.advance(state, human_input, params)

    _apply_step_to_session(assistance_session, step)
    await db.commit()

    logger.info(
        "Assistance advanced: session_id=%s, type=%s, is_terminal=%s",
        session_id,
        step.type,
        step.is_terminal,
    )

    return _step_to_response(session_id, step)
