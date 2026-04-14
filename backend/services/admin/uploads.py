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
    questions_added = 0

    for row in reader:
        validate_csv_required_fields(row, required_fields)
        db.add(
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
        questions_added += 1

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
