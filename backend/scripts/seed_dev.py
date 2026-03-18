from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import func
from sqlmodel import Session, create_engine, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config import get_settings  # noqa: E402
from models import Experiment, ProlificStudyStatus, Question  # noqa: E402
from services.admin.prolific import (  # noqa: E402
    build_completion_url,
    create_study,
    generate_completion_code,
)


def main() -> int:
    settings = get_settings()

    if not settings.seeding.enabled:
        print("Skipping seed run because [seeding].enabled is false.")
        return 0

    if not settings.prolific.api_token:
        print("Error: PROLIFIC__API_TOKEN is required for seeding (Prolific study creation).")
        return 1

    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)

    with Session(engine) as session:
        experiment = session.exec(
            select(Experiment)
            .where(Experiment.name == settings.seeding.experiment_name)
            .order_by(Experiment.id)
        ).first()

        if experiment is None:
            completion_code = generate_completion_code()
            completion_url = build_completion_url(completion_code)

            experiment = Experiment(
                name=settings.seeding.experiment_name,
                num_ratings_per_question=settings.seeding.num_ratings_per_question,
                prolific_completion_url=completion_url,
                prolific_completion_code=completion_code,
            )
            session.add(experiment)
            session.flush()  # assigns ID for external_study_url

            external_study_url = (
                f"{settings.app.site_url}/rate"
                f"?experiment_id={experiment.id}"
                f"&PROLIFIC_PID={{{{%PROLIFIC_PID%}}}}"
                f"&STUDY_ID={{{{%STUDY_ID%}}}}"
                f"&SESSION_ID={{{{%SESSION_ID%}}}}"
            )

            result = asyncio.run(
                create_study(
                    settings=settings.prolific,
                    name=settings.seeding.experiment_name,
                    description=f"Seed study for {settings.seeding.experiment_name}",
                    external_study_url=external_study_url,
                    estimated_completion_time=10,
                    reward=100,
                    total_available_places=settings.seeding.num_ratings_per_question,
                    completion_code=completion_code,
                )
            )
            experiment.prolific_study_id = result["id"]
            experiment.prolific_study_status = ProlificStudyStatus(
                result.get("status", "UNPUBLISHED")
            )

            session.commit()
            session.refresh(experiment)
            print(
                "Created seed experiment "
                f"id={experiment.id} name={settings.seeding.experiment_name!r} "
                f"prolific_study_id={experiment.prolific_study_id}"
            )

        existing_count = session.exec(
            select(func.count())
            .select_from(Question)
            .where(Question.experiment_id == experiment.id)
        ).one()

        if existing_count >= settings.seeding.question_count:
            print(
                "Seed already satisfies configured question count "
                f"({existing_count}/{settings.seeding.question_count})."
            )
            return 0

        for index in range(existing_count + 1, settings.seeding.question_count + 1):
            session.add(
                Question(
                    experiment_id=experiment.id,
                    question_id=f"seed-{index}",
                    question_text=f"Seed question {index}",
                    gt_answer="",
                    options="Yes|No",
                    question_type="MC",
                    extra_data="{}",
                )
            )

        session.commit()
        print(
            "Seeded questions to target count "
            f"{settings.seeding.question_count} for experiment_id={experiment.id}."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
