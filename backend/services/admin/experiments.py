from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from models import Experiment, ProlificStudyStatus, Question, Rating, Rater
from schemas import ExperimentCreate, ExperimentResponse
from .mappers import build_experiment_response
from .prolific import (
    build_completion_url,
    create_study,
    delete_study,
    generate_completion_code,
    publish_study,
)
from .queries import fetch_experiment_or_404, fetch_total_questions_for_experiment

logger = logging.getLogger(__name__)


async def create_experiment(
    payload: ExperimentCreate,
    db: AsyncSession,
) -> ExperimentResponse:
    settings = get_settings()

    if not settings.prolific.api_token:
        raise HTTPException(
            status_code=400,
            detail="Prolific API token is not configured. Set PROLIFIC__API_TOKEN to create experiments.",
        )

    completion_code = generate_completion_code()
    completion_url = build_completion_url(completion_code)

    db_experiment = Experiment(
        name=payload.name,
        num_ratings_per_question=payload.num_ratings_per_question,
        prolific_completion_url=completion_url,
        prolific_completion_code=completion_code,
    )
    db.add(db_experiment)
    await db.flush()  # assigns ID without committing

    # Build the external study URL with Prolific placeholders
    external_study_url = (
        f"{settings.app.site_url}/rate"
        f"?experiment_id={db_experiment.id}"
        f"&PROLIFIC_PID={{{{%PROLIFIC_PID%}}}}"
        f"&STUDY_ID={{{{%STUDY_ID%}}}}"
        f"&SESSION_ID={{{{%SESSION_ID%}}}}"
    )

    try:
        result = await create_study(
            settings=settings.prolific,
            name=payload.name,
            description=payload.prolific.description,
            external_study_url=external_study_url,
            estimated_completion_time=payload.prolific.estimated_completion_time,
            reward=payload.prolific.reward,
            total_available_places=payload.prolific.total_available_places,
            completion_code=completion_code,
            device_compatibility=payload.prolific.device_compatibility,
        )
    except Exception:
        await db.rollback()
        logger.exception("Failed to create Prolific study for experiment '%s'", payload.name)
        raise HTTPException(
            status_code=502,
            detail="Failed to create study on Prolific. Please check your API token and try again.",
        )

    db_experiment.prolific_study_id = result["id"]
    db_experiment.prolific_study_status = ProlificStudyStatus(result.get("status", "UNPUBLISHED"))
    await db.commit()
    await db.refresh(db_experiment)

    logger.info(
        "Created experiment id=%s with Prolific study_id=%s",
        db_experiment.id,
        result["id"],
    )
    return build_experiment_response(db_experiment, question_count=0, rating_count=0)


async def list_experiments(
    skip: int,
    limit: int,
    db: AsyncSession,
) -> list[ExperimentResponse]:
    question_counts = (
        select(
            Question.experiment_id,
            func.count(Question.id).label("question_count"),
        )
        .group_by(Question.experiment_id)
        .subquery()
    )

    rating_counts = (
        select(
            Question.experiment_id,
            func.count(Rating.id).label("rating_count"),
        )
        .join(Rating, Rating.question_id == Question.id)
        .group_by(Question.experiment_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(
                Experiment,
                func.coalesce(question_counts.c.question_count, 0).label("question_count"),
                func.coalesce(rating_counts.c.rating_count, 0).label("rating_count"),
            )
            .outerjoin(question_counts, Experiment.id == question_counts.c.experiment_id)
            .outerjoin(rating_counts, Experiment.id == rating_counts.c.experiment_id)
            .order_by(Experiment.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    ).all()

    return [
        build_experiment_response(
            experiment,
            question_count=int(question_count or 0),
            rating_count=int(rating_count or 0),
        )
        for experiment, question_count, rating_count in rows
    ]


async def delete_experiment(
    experiment_id: int,
    db: AsyncSession,
) -> dict[str, str]:
    experiment = await fetch_experiment_or_404(experiment_id, db)
    experiment_name = experiment.name

    # Clean up Prolific study if one exists
    if experiment.prolific_study_id:
        try:
            await delete_study(
                settings=get_settings().prolific,
                study_id=experiment.prolific_study_id,
            )
            logger.info("Deleted Prolific study: %s", experiment.prolific_study_id)
        except Exception:
            logger.exception(
                "Failed to delete Prolific study %s (continuing with local delete)",
                experiment.prolific_study_id,
            )

    await db.delete(experiment)
    await db.commit()

    logger.info("Deleted experiment: id=%s, name=%s", experiment_id, experiment_name)
    return {"message": "Experiment deleted successfully"}


async def publish_prolific_study(
    experiment_id: int,
    db: AsyncSession,
) -> dict[str, str]:
    settings = get_settings()
    experiment = await fetch_experiment_or_404(experiment_id, db)
    if not experiment.prolific_study_id:
        raise HTTPException(status_code=400, detail="This experiment has no linked Prolific study")

    try:
        result = await publish_study(
            settings=settings.prolific,
            study_id=experiment.prolific_study_id,
        )
    except Exception:
        logger.exception(
            "Failed to publish Prolific study %s for experiment %s",
            experiment.prolific_study_id,
            experiment_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Failed to publish study on Prolific. Please try again.",
        )

    experiment.prolific_study_status = ProlificStudyStatus(result.get("status", "ACTIVE"))
    await db.commit()

    logger.info(
        "Published Prolific study %s for experiment %s", experiment.prolific_study_id, experiment_id
    )
    return {"message": "Study published on Prolific", "status": experiment.prolific_study_status}


async def get_experiment_stats(
    experiment_id: int,
    db: AsyncSession,
    *,
    include_preview: bool = False,
) -> dict[str, Any]:
    experiment = await fetch_experiment_or_404(experiment_id, db)

    total_questions = await fetch_total_questions_for_experiment(experiment_id, db)

    ratings_stmt = (
        select(func.count(Rating.id))
        .join(Question, Rating.question_id == Question.id)
        .join(Rater, Rating.rater_id == Rater.id)
        .where(Question.experiment_id == experiment_id)
    )
    raters_stmt = select(func.count(Rater.id)).where(Rater.experiment_id == experiment_id)
    complete_stmt = (
        select(Question.id)
        .join(Rating, Rating.question_id == Question.id)
        .join(Rater, Rating.rater_id == Rater.id)
        .where(Question.experiment_id == experiment_id)
        .group_by(Question.id)
        .having(func.count(Rating.id) >= experiment.num_ratings_per_question)
    )

    if not include_preview:
        preview_filter = Rater.is_preview == False  # noqa: E712
        ratings_stmt = ratings_stmt.where(preview_filter)
        raters_stmt = raters_stmt.where(preview_filter)
        complete_stmt = complete_stmt.where(preview_filter)

    total_ratings = (await db.execute(ratings_stmt)).scalar_one()
    total_raters = (await db.execute(raters_stmt)).scalar_one()
    questions_complete = len((await db.execute(complete_stmt)).all())

    return {
        "experiment_name": experiment.name,
        "total_questions": total_questions,
        "questions_complete": int(questions_complete),
        "total_ratings": int(total_ratings or 0),
        "total_raters": int(total_raters or 0),
        "target_ratings_per_question": experiment.num_ratings_per_question,
    }
