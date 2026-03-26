from __future__ import annotations

from datetime import datetime, timedelta

from models import ExperimentType, Question, SESSION_DURATION_MINUTES
from schemas import QuestionResponse, RaterStartResponse


def build_session_end_time(session_start: datetime) -> datetime:
    return session_start + timedelta(minutes=SESSION_DURATION_MINUTES)


def build_question_response(question: Question) -> QuestionResponse:
    return QuestionResponse(
        id=question.id,
        question_id=question.question_id,
        question_text=question.question_text,
        options=question.options,
        question_type=question.question_type,
    )


def build_rater_start_response(
    *,
    rater_id: int,
    session_start: datetime,
    experiment_name: str,
    completion_url: str | None,
    experiment_type: ExperimentType = ExperimentType.RATING,
    delegation_task_id: str | None = None,
    rater_session_token: str,
) -> RaterStartResponse:
    return RaterStartResponse(
        rater_id=rater_id,
        session_start=session_start,
        session_end_time=build_session_end_time(session_start),
        experiment_name=experiment_name,
        completion_url=completion_url,
        experiment_type=experiment_type,
        delegation_task_id=delegation_task_id,
        rater_session_token=rater_session_token,
    )
