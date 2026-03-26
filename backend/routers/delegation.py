from __future__ import annotations

from dataclasses import dataclass
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from database import get_session
from models import Experiment, InteractionLog, Rater
from questions import QUESTIONS
from routers.deps import RaterSession, require_rater_session
from schemas import (
    ChatMessage,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    DelegationSubmit,
    DelegationSubmitResponse,
    DelegationTaskResponse,
    SubtaskData,
)
from services.openai_client import get_chat_response
from services.rater.queries import fetch_experiment_or_404, fetch_rater_or_404
from services.rater.validators import validate_rater_session_is_active

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delegation", tags=["delegation"])


@dataclass
class DelegationContext:
    rater: Rater
    experiment: Experiment
    task_id: str
    task: dict


async def get_delegation_context(
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
) -> DelegationContext:
    rater = await fetch_rater_or_404(session.rater_id, db)
    await validate_rater_session_is_active(rater, db)

    experiment = await fetch_experiment_or_404(rater.experiment_id, db)
    task_id = (rater.delegation_task_id or "").strip()
    if not task_id:
        raise HTTPException(status_code=403, detail="No delegation task assigned")

    task = QUESTIONS.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return DelegationContext(
        rater=rater,
        experiment=experiment,
        task_id=task_id,
        task=task,
    )


def validate_request_matches_context(
    *,
    pid: str,
    experiment_id: int,
    task_id: str,
    ctx: DelegationContext,
) -> None:
    if pid != ctx.rater.prolific_id:
        raise HTTPException(status_code=403, detail="Invalid delegation session")
    if experiment_id != ctx.experiment.id:
        raise HTTPException(status_code=403, detail="Invalid delegation session")
    if task_id != ctx.task_id:
        raise HTTPException(status_code=403, detail="Invalid delegation session")


@router.get("/task/{task_id}", response_model=DelegationTaskResponse)
async def get_task(task_id: str, ctx: DelegationContext = Depends(get_delegation_context)):
    if task_id != ctx.task_id:
        raise HTTPException(status_code=403, detail="Invalid delegation session")

    task = ctx.task
    return DelegationTaskResponse(
        id=task["id"],
        instructions=task["instructions"],
        question=task["question"],
        delegation_data=[SubtaskData(**s) for s in task["delegation_data"]],
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    ctx: DelegationContext = Depends(get_delegation_context),
    db: AsyncSession = Depends(get_session),
):
    if ctx.experiment.experiment_type != "chat":
        raise HTTPException(status_code=403, detail="Chat is not enabled for this session")

    validate_request_matches_context(
        pid=request.pid,
        experiment_id=request.experiment_id,
        task_id=request.task_id,
        ctx=ctx,
    )

    try:
        messages = [{"role": m.role, "content": m.content} for m in request.message_history]
        ai_response = await get_chat_response(
            messages,
            ctx.task["question"],
            ctx.task["instructions"],
        )
    except Exception:
        logger.exception("OpenAI error for task_id=%s", ctx.task_id)
        ai_response = "Sorry, I encountered an error processing your request. Please try again."

    full_conversation = [m.model_dump() for m in request.message_history]
    full_conversation.append({"role": "assistant", "content": ai_response})

    # Upsert: one log entry per participant+task
    stmt = (
        select(InteractionLog)
        .where(InteractionLog.prolific_pid == ctx.rater.prolific_id)
        .where(InteractionLog.task_id == ctx.task_id)
        .where(InteractionLog.condition == "chat")
        .where(InteractionLog.experiment_id == ctx.experiment.id)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.payload = json.dumps(full_conversation)
        db.add(existing)
    else:
        db.add(
            InteractionLog(
                prolific_pid=ctx.rater.prolific_id,
                experiment_id=ctx.experiment.id,
                task_id=ctx.task_id,
                condition="chat",
                interaction_type="chat_message",
                payload=json.dumps(full_conversation),
            )
        )
    await db.commit()

    return ChatResponse(ai_message=ai_response)


@router.get("/chat-history", response_model=ChatHistoryResponse)
async def get_chat_history(
    ctx: DelegationContext = Depends(get_delegation_context),
    db: AsyncSession = Depends(get_session),
):
    if ctx.experiment.experiment_type != "chat":
        raise HTTPException(status_code=403, detail="Chat is not enabled for this session")

    stmt = (
        select(InteractionLog)
        .where(InteractionLog.prolific_pid == ctx.rater.prolific_id)
        .where(InteractionLog.task_id == ctx.task_id)
        .where(InteractionLog.condition == "chat")
        .where(InteractionLog.experiment_id == ctx.experiment.id)
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if not existing:
        return ChatHistoryResponse(messages=[])

    try:
        payload = json.loads(existing.payload)
    except json.JSONDecodeError:
        logger.warning("Invalid chat history payload for task_id=%s", ctx.task_id)
        return ChatHistoryResponse(messages=[])

    if not isinstance(payload, list):
        logger.warning("Unexpected chat history payload type for task_id=%s", ctx.task_id)
        return ChatHistoryResponse(messages=[])

    try:
        messages = [ChatMessage.model_validate(message) for message in payload]
    except ValidationError:
        logger.warning("Invalid chat history message payload for task_id=%s", ctx.task_id)
        return ChatHistoryResponse(messages=[])

    return ChatHistoryResponse(messages=messages)


@router.post("/submit", response_model=DelegationSubmitResponse)
async def submit_delegation(
    request: DelegationSubmit,
    ctx: DelegationContext = Depends(get_delegation_context),
    db: AsyncSession = Depends(get_session),
):
    if ctx.experiment.experiment_type != "delegation":
        raise HTTPException(status_code=403, detail="Delegation is not enabled for this session")

    validate_request_matches_context(
        pid=request.pid,
        experiment_id=request.experiment_id,
        task_id=request.task_id,
        ctx=ctx,
    )

    stmt = (
        select(InteractionLog)
        .where(InteractionLog.prolific_pid == ctx.rater.prolific_id)
        .where(InteractionLog.task_id == ctx.task_id)
        .where(InteractionLog.condition == "delegation")
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.payload = json.dumps(request.subtask_inputs)
        db.add(existing)
    else:
        db.add(
            InteractionLog(
                prolific_pid=ctx.rater.prolific_id,
                experiment_id=ctx.experiment.id,
                task_id=ctx.task_id,
                condition="delegation",
                interaction_type="delegation_submission",
                payload=json.dumps(request.subtask_inputs),
            )
        )
    await db.commit()

    return DelegationSubmitResponse(status="success")
