from __future__ import annotations

import csv
import io
import logging
from typing import Any

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Question, Upload
from .mappers import build_upload_response
from .queries import fetch_experiment_or_404
from .validators import validate_csv_required_fields, validate_csv_upload

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


async def upload_questions_csv(
    experiment_id: int,
    file: UploadFile,
    db: AsyncSession,
) -> dict[str, str]:
    await fetch_experiment_or_404(experiment_id, db)
    validate_csv_upload(file)

    content_bytes = await file.read()
    if len(content_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit")

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded") from exc

    reader = csv.DictReader(io.StringIO(content))
    required_fields = ["question_id", "question_text"]
    rows = list(reader)
    for row in rows:
        validate_csv_required_fields(row, required_fields)

    new_questions: list[Question] = []
    for row in rows:
        new_questions.append(
            Question(
                experiment_id=experiment_id,
                question_id=row["question_id"],
                question_text=row["question_text"],
                gt_answer=row.get("gt_answer") or "",
                options=row.get("options") or "",
                question_type=row.get("question_type") or "MC",
                extra_data=row.get("metadata") or "{}",
            )
        )
        db.add(new_questions[-1])

    # Flush so newly inserted rows have DB ids before we resolve parent references.
    await db.flush()

    parent_refs = {
        (row.get("parent_question_id") or "").strip()
        for row in rows
        if (row.get("parent_question_id") or "").strip()
    }
    if parent_refs:
        # Build {question_id_string -> db id} for this experiment, covering both rows
        # just inserted and any pre-existing ones from earlier uploads.
        existing = (
            await db.execute(
                select(Question.question_id, Question.id).where(
                    Question.experiment_id == experiment_id
                )
            )
        ).all()
        question_id_to_db_id: dict[str, int] = {}
        for qid_string, db_id in existing:
            # Last write wins on duplicate question_id strings — questions already
            # allow duplicates within an experiment, and the CSV-string parent ref
            # is inherently ambiguous in that case. We pick whichever the DB returns.
            question_id_to_db_id[qid_string] = db_id

        for question, row in zip(new_questions, rows):
            parent_ref = (row.get("parent_question_id") or "").strip()
            if not parent_ref:
                continue
            if parent_ref == question.question_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Question '{question.question_id}' cannot reference itself as parent",
                )
            parent_db_id = question_id_to_db_id.get(parent_ref)
            if parent_db_id is None:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"parent_question_id '{parent_ref}' (referenced by '{question.question_id}') "
                        f"does not match any question in this experiment"
                    ),
                )
            question.parent_question_id = parent_db_id

    questions_added = len(new_questions)
    db.add(
        Upload(
            experiment_id=experiment_id,
            filename=file.filename,
            question_count=questions_added,
        )
    )
    await db.commit()

    logger.info(
        "Question batch uploaded",
        extra={
            "attributes": {
                "experiment_id": experiment_id,
                "question_count": questions_added,
                "filename": file.filename,
            }
        },
    )

    return {"message": f"Uploaded {questions_added} questions"}


async def list_uploads(
    experiment_id: int,
    skip: int,
    limit: int,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    await fetch_experiment_or_404(experiment_id, db)

    uploads = (
        (
            await db.execute(
                select(Upload)
                .where(Upload.experiment_id == experiment_id)
                .order_by(Upload.uploaded_at.desc())
                .offset(skip)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    return [build_upload_response(upload) for upload in uploads]
