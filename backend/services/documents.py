from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, UploadFile
from openai import AsyncOpenAI
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models as qdrant
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import Settings, get_settings
from models import ExperimentDocument, ExperimentDocumentChunk
from schemas import (
    ExperimentDocumentPageResponse,
    ExperimentDocumentResponse,
    ExperimentDocumentSearchResponse,
    ExperimentDocumentSearchResult,
)
from services.queries import (
    fetch_experiment_document_or_404,
    fetch_experiment_or_404,
    fetch_question_or_404,
    fetch_rater_or_404,
)

MAX_DOCUMENT_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_DOCUMENT_SUFFIXES = {".txt", ".md"}
logger = logging.getLogger(__name__)


@dataclass
class ChunkPayload:
    chunk_index: int
    text: str
    char_start: int
    char_end: int


def _normalize_text(raw: str) -> str:
    return raw.replace("\r\n", "\n").replace("\r", "\n")


def _chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[ChunkPayload]:
    normalized = _normalize_text(text).strip()
    if not normalized:
        return []

    chunks: list[ChunkPayload] = []
    cursor = 0
    chunk_index = 0
    text_length = len(normalized)

    while cursor < text_length:
        target_end = min(cursor + chunk_size, text_length)
        end = target_end
        if target_end < text_length:
            boundary = normalized.rfind("\n\n", cursor, target_end)
            if boundary > cursor + chunk_size // 3:
                end = boundary + 2
            else:
                boundary = normalized.rfind("\n", cursor, target_end)
                if boundary > cursor + chunk_size // 3:
                    end = boundary + 1

        chunk_text = normalized[cursor:end].strip()
        if chunk_text:
            chunks.append(
                ChunkPayload(
                    chunk_index=chunk_index,
                    text=chunk_text,
                    char_start=cursor,
                    char_end=end,
                )
            )
            chunk_index += 1

        if end >= text_length:
            break
        cursor = max(end - overlap, cursor + 1)

    return chunks


def _collection_name(experiment_id: int, settings: Settings) -> str:
    return f"{settings.vector_store.collection_prefix}_{experiment_id}"


def _embedding_api_key(settings: Settings) -> str:
    return (settings.embeddings.api_key or settings.llm.api_key).strip()


def embeddings_enabled(settings: Settings | None = None) -> bool:
    active = settings or get_settings()
    return bool(_embedding_api_key(active))


@lru_cache(maxsize=1)
def _get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=get_settings().vector_store.url)


@lru_cache(maxsize=1)
def _get_embedding_client() -> AsyncOpenAI:
    settings = get_settings()
    api_key = _embedding_api_key(settings)
    if not api_key:
        raise RuntimeError("Embeddings API key is not configured")
    return AsyncOpenAI(
        api_key=api_key,
        base_url=settings.embeddings.base_url,
    )


async def _ensure_collection(experiment_id: int, settings: Settings) -> None:
    client = _get_qdrant_client()
    collection_name = _collection_name(experiment_id, settings)
    collections = await client.get_collections()
    if any(collection.name == collection_name for collection in collections.collections):
        return
    await client.create_collection(
        collection_name=collection_name,
        vectors_config=qdrant.VectorParams(
            size=settings.embeddings.vector_size,
            distance=qdrant.Distance.COSINE,
        ),
    )


async def _embed_texts(texts: list[str], settings: Settings) -> list[list[float]]:
    if not texts:
        return []
    response = await _get_embedding_client().embeddings.create(
        model=settings.embeddings.model,
        input=texts,
    )
    return [item.embedding for item in response.data]


async def _upsert_vectors(
    *,
    experiment_id: int,
    document_id: int,
    chunks: list[ExperimentDocumentChunk],
    settings: Settings,
) -> None:
    if not embeddings_enabled(settings):
        return

    await _ensure_collection(experiment_id, settings)
    vectors = await _embed_texts([chunk.text for chunk in chunks], settings)
    points = [
        qdrant.PointStruct(
            id=chunk.id,
            vector=vector,
            payload={
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "experiment_id": experiment_id,
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    await _get_qdrant_client().upsert(
        collection_name=_collection_name(experiment_id, settings),
        points=points,
    )


async def _delete_vectors(*, experiment_id: int, document_id: int, settings: Settings) -> None:
    if not embeddings_enabled(settings):
        return

    await _ensure_collection(experiment_id, settings)
    await _get_qdrant_client().delete(
        collection_name=_collection_name(experiment_id, settings),
        points_selector=qdrant.FilterSelector(
            filter=qdrant.Filter(
                must=[
                    qdrant.FieldCondition(
                        key="document_id",
                        match=qdrant.MatchValue(value=document_id),
                    )
                ]
            )
        ),
    )


def _score_lexical(query: str, text: str) -> float:
    lowered_query = query.lower().strip()
    lowered_text = text.lower()
    if not lowered_query:
        return 0.0

    score = 0.0
    if lowered_query in lowered_text:
        score += 5.0

    for token in [part for part in lowered_query.split() if part]:
        occurrences = lowered_text.count(token)
        if occurrences:
            score += min(occurrences, 5)

    return score


async def upload_experiment_document(
    *,
    experiment_id: int,
    file: UploadFile,
    db: AsyncSession,
    settings: Settings,
) -> dict[str, str]:
    await fetch_experiment_or_404(experiment_id, db)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_DOCUMENT_SUFFIXES:
        raise HTTPException(status_code=400, detail="Document must be a .txt or .md file")

    content_bytes = await file.read()
    if len(content_bytes) > MAX_DOCUMENT_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Document exceeds 50MB limit")

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="Document must be UTF-8 encoded") from exc

    chunks = _chunk_text(
        content,
        chunk_size=settings.vector_store.chunk_size_chars,
        overlap=settings.vector_store.chunk_overlap_chars,
    )
    if not chunks:
        raise HTTPException(status_code=400, detail="Document has no searchable text")

    document = ExperimentDocument(
        experiment_id=experiment_id,
        title=Path(file.filename or "document").stem,
        source_filename=file.filename or "document.txt",
        content_type=file.content_type or "text/plain",
        chunk_count=len(chunks),
    )
    db.add(document)
    await db.flush()

    chunk_models = [
        ExperimentDocumentChunk(
            document_id=document.id,
            experiment_id=experiment_id,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        for chunk in chunks
    ]
    db.add_all(chunk_models)
    await db.flush()

    try:
        await _upsert_vectors(
            experiment_id=experiment_id,
            document_id=document.id,
            chunks=chunk_models,
            settings=settings,
        )
    except Exception:
        logger.exception(
            "Vector upsert failed for experiment_id=%s document=%s; keeping lexical browse/search only",
            experiment_id,
            file.filename,
        )

    await db.commit()

    return {"message": f"Uploaded document '{document.title}' with {len(chunk_models)} chunks"}


async def list_experiment_documents(
    *,
    experiment_id: int,
    db: AsyncSession,
) -> list[ExperimentDocumentResponse]:
    await fetch_experiment_or_404(experiment_id, db)
    rows = (
        await db.execute(
            select(ExperimentDocument)
            .where(ExperimentDocument.experiment_id == experiment_id)
            .order_by(ExperimentDocument.created_at.desc())
        )
    ).scalars().all()
    return [ExperimentDocumentResponse.model_validate(row) for row in rows]


async def get_document_page_for_rater(
    *,
    rater_id: int,
    question_id: int,
    document_id: int,
    page: int,
    page_size: int,
    db: AsyncSession,
    settings: Settings,
) -> ExperimentDocumentPageResponse:
    rater = await fetch_rater_or_404(rater_id, db)
    question = await fetch_question_or_404(question_id, db)
    document = await fetch_experiment_document_or_404(document_id, db)

    if question.experiment_id != rater.experiment_id or document.experiment_id != rater.experiment_id:
        raise HTTPException(status_code=403, detail="Question or document is outside this session")

    safe_page_size = max(1, min(page_size, settings.vector_store.browse_page_size_chunks * 3))
    total_pages = max(1, math.ceil(document.chunk_count / safe_page_size))
    safe_page = max(1, min(page, total_pages))
    offset = (safe_page - 1) * safe_page_size

    chunks = (
        await db.execute(
            select(ExperimentDocumentChunk)
            .where(ExperimentDocumentChunk.document_id == document.id)
            .order_by(ExperimentDocumentChunk.chunk_index.asc())
            .offset(offset)
            .limit(safe_page_size)
        )
    ).scalars().all()

    return ExperimentDocumentPageResponse(
        document_id=document.id,
        title=document.title,
        page=safe_page,
        page_size=safe_page_size,
        total_pages=total_pages,
        total_chunks=document.chunk_count,
        chunks=chunks,
    )


async def list_documents_for_rater(
    *,
    rater_id: int,
    question_id: int,
    db: AsyncSession,
) -> list[ExperimentDocumentResponse]:
    rater = await fetch_rater_or_404(rater_id, db)
    question = await fetch_question_or_404(question_id, db)
    if question.experiment_id != rater.experiment_id:
        raise HTTPException(status_code=403, detail="Question does not belong to this session")
    return await list_experiment_documents(experiment_id=rater.experiment_id, db=db)


async def search_documents_for_rater(
    *,
    rater_id: int,
    question_id: int,
    document_id: int | None,
    query: str,
    mode: str,
    limit: int,
    db: AsyncSession,
    settings: Settings,
) -> ExperimentDocumentSearchResponse:
    rater = await fetch_rater_or_404(rater_id, db)
    question = await fetch_question_or_404(question_id, db)
    if question.experiment_id != rater.experiment_id:
        raise HTTPException(status_code=403, detail="Question does not belong to this session")
    if document_id is not None:
        document = await fetch_experiment_document_or_404(document_id, db)
        if document.experiment_id != rater.experiment_id:
            raise HTTPException(status_code=403, detail="Document is outside this session")

    normalized_mode = mode if mode in {"lexical", "semantic", "hybrid"} else "hybrid"
    safe_limit = max(1, min(limit, 25))
    embeddings_ready = embeddings_enabled(settings)

    if normalized_mode == "semantic" and not embeddings_ready:
        raise HTTPException(status_code=400, detail="Semantic search is not configured")

    chunks_stmt = (
        select(ExperimentDocumentChunk, ExperimentDocument.title)
        .join(ExperimentDocument, ExperimentDocument.id == ExperimentDocumentChunk.document_id)
        .where(ExperimentDocumentChunk.experiment_id == rater.experiment_id)
    )
    if document_id is not None:
        chunks_stmt = chunks_stmt.where(ExperimentDocumentChunk.document_id == document_id)

    chunks = (await db.execute(chunks_stmt)).all()

    lexical_scores: dict[int, float] = {}
    chunk_lookup: dict[int, tuple[ExperimentDocumentChunk, str]] = {}
    for chunk, title in chunks:
        chunk_lookup[chunk.id] = (chunk, title)
        lexical_scores[chunk.id] = _score_lexical(query, chunk.text)

    semantic_scores: dict[int, float] = defaultdict(float)
    if normalized_mode in {"semantic", "hybrid"} and embeddings_ready:
        try:
            await _ensure_collection(rater.experiment_id, settings)
            vector = (await _embed_texts([query], settings))[0]
            search_filter = None
            if document_id is not None:
                search_filter = qdrant.Filter(
                    must=[
                        qdrant.FieldCondition(
                            key="document_id",
                            match=qdrant.MatchValue(value=document_id),
                        )
                    ]
                )
            hits = await _get_qdrant_client().search(
                collection_name=_collection_name(rater.experiment_id, settings),
                query_vector=vector,
                query_filter=search_filter,
                limit=safe_limit * 3,
            )
            for hit in hits:
                semantic_scores[int(hit.id)] = float(hit.score or 0.0)
        except Exception:
            if normalized_mode == "semantic":
                raise HTTPException(
                    status_code=503,
                    detail="Semantic search is temporarily unavailable",
                ) from None
            logger.exception(
                "Semantic document search failed for experiment_id=%s question_id=%s; falling back to lexical results",
                rater.experiment_id,
                question_id,
            )

    combined: list[tuple[ExperimentDocumentChunk, str, float]] = []
    for chunk_id, (chunk, title) in chunk_lookup.items():
        lexical = lexical_scores.get(chunk_id, 0.0)
        semantic = semantic_scores.get(chunk_id, 0.0)
        if normalized_mode == "lexical":
            score = lexical
        elif normalized_mode == "semantic":
            score = semantic
        else:
            score = lexical + (semantic * 5.0)
        if score > 0:
            combined.append((chunk, title, score))

    combined.sort(key=lambda item: item[2], reverse=True)
    results = [
        ExperimentDocumentSearchResult(
            chunk_id=chunk.id,
            document_id=chunk.document_id,
            document_title=title,
            chunk_index=chunk.chunk_index,
            score=round(score, 4),
            text=chunk.text,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
        )
        for chunk, title, score in combined[:safe_limit]
    ]

    return ExperimentDocumentSearchResponse(
        query=query,
        mode=normalized_mode,  # type: ignore[arg-type]
        results=results,
    )


async def delete_experiment_documents(
    *,
    experiment_id: int,
    db: AsyncSession,
    settings: Settings,
) -> None:
    documents = (
        await db.execute(
            select(ExperimentDocument.id).where(ExperimentDocument.experiment_id == experiment_id)
        )
    ).scalars().all()
    for document_id in documents:
        await _delete_vectors(
            experiment_id=experiment_id,
            document_id=document_id,
            settings=settings,
        )
    await db.execute(delete(ExperimentDocument).where(ExperimentDocument.experiment_id == experiment_id))
    await db.commit()
