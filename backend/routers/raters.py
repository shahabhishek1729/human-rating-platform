from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from database import get_session
from schemas import (
    AssistanceAdvanceRequest,
    ExperimentDocumentPageResponse,
    ExperimentDocumentResponse,
    ExperimentDocumentSearchResponse,
    AssistanceStartRequest,
    AssistanceStepResponse,
    QuestionResponse,
    RaterStartResponse,
    RatingResponse,
    RatingSubmit,
    SessionStatusResponse,
)
from services import assistance, rater
from services.documents import (
    get_document_page_for_rater,
    list_documents_for_rater,
    search_documents_for_rater,
)

from .deps import RaterSession, require_rater_session

router = APIRouter(prefix="/raters", tags=["raters"])


@router.post("/start", response_model=RaterStartResponse)
async def start_session(
    experiment_id: int = Query(...),
    PROLIFIC_PID: str = Query(...),
    STUDY_ID: str = Query(...),
    SESSION_ID: str = Query(...),
    preview: bool = Query(False),
    settings: Settings = Depends(get_settings),
    db: AsyncSession = Depends(get_session),
):
    return await rater.start_session(
        settings=settings,
        experiment_id=experiment_id,
        prolific_pid=PROLIFIC_PID,
        study_id=STUDY_ID,
        session_id=SESSION_ID,
        is_preview=preview,
        db=db,
    )


@router.get("/next-question", response_model=Optional[QuestionResponse])
async def get_next_question(
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await rater.get_next_question(rater_id=session.rater_id, db=db)


@router.post("/submit", response_model=RatingResponse)
async def submit_rating(
    rating: RatingSubmit,
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await rater.submit_rating(payload=rating, rater_id=session.rater_id, db=db)


@router.get("/documents", response_model=list[ExperimentDocumentResponse])
async def list_documents(
    question_id: int = Query(...),
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await list_documents_for_rater(
        rater_id=session.rater_id,
        question_id=question_id,
        db=db,
    )


@router.get("/documents/{document_id}/page", response_model=ExperimentDocumentPageResponse)
async def get_document_page(
    document_id: int,
    question_id: int = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(8, ge=1, le=50),
    settings: Settings = Depends(get_settings),
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await get_document_page_for_rater(
        rater_id=session.rater_id,
        question_id=question_id,
        document_id=document_id,
        page=page,
        page_size=page_size,
        db=db,
        settings=settings,
    )


@router.get("/documents/search", response_model=ExperimentDocumentSearchResponse)
async def search_documents(
    question_id: int = Query(...),
    document_id: int | None = Query(None),
    q: str = Query(..., min_length=1),
    mode: str = Query("hybrid"),
    limit: int = Query(8, ge=1, le=25),
    settings: Settings = Depends(get_settings),
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await search_documents_for_rater(
        rater_id=session.rater_id,
        question_id=question_id,
        document_id=document_id,
        query=q,
        mode=mode,
        limit=limit,
        db=db,
        settings=settings,
    )


@router.get("/session-status", response_model=SessionStatusResponse)
async def get_session_status(
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await rater.get_session_status(rater_id=session.rater_id, db=db)


@router.post("/end-session")
async def end_session(
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await rater.end_session(rater_id=session.rater_id, db=db)


@router.post("/assistance/start", response_model=AssistanceStepResponse)
async def start_assistance(
    body: AssistanceStartRequest,
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await assistance.start_assistance(
        rater_id=session.rater_id,
        question_id=body.question_id,
        db=db,
    )


@router.post("/assistance/advance", response_model=AssistanceStepResponse)
async def advance_assistance(
    body: AssistanceAdvanceRequest,
    session: RaterSession = Depends(require_rater_session),
    db: AsyncSession = Depends(get_session),
):
    return await assistance.advance_assistance(
        rater_id=session.rater_id,
        session_id=body.session_id,
        human_input=body.human_input,
        db=db,
    )
