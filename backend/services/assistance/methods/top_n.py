"""Top-N answer assistance method.

The method asks an LLM to rank likely answers for the current question and
returns the top N candidates as static guidance. It is intentionally one-shot:
raters can review the suggestions, then make their own final rating.

assistance_params:
    model: LLM to use for ranking (default: settings.llm.default_model)
    n:     Number of candidates to show (default: 3, range 1-10)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from config import get_settings
from models import Question

from ..base import AssistanceMethod, InteractionStep, StepType
from ..llm import complete

logger = logging.getLogger(__name__)

_DEFAULT_TOP_N = 3
_MAX_TOP_N = 10

_SYSTEM_PROMPT = """\
You help human raters answer evaluation questions. Rank the most likely answers
without hiding uncertainty. Use only the question and options provided by the
user; do not invent options for multiple-choice questions.

Return JSON only, with this shape:
{"candidates":[{"answer":"...","confidence":0-100,"rationale":"short reason"}]}
"""


def _parse_options(raw_options: str | None) -> list[str]:
    if not raw_options:
        return []
    delimiter = "|" if "|" in raw_options else ","
    return [option.strip() for option in raw_options.split(delimiter) if option.strip()]


def _clamp_top_n(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        n = _DEFAULT_TOP_N
    return max(1, min(_MAX_TOP_N, n))


def _strip_markdown_json(raw: str) -> str:
    return re.sub(r"```json?\n?|```\n?", "", raw).strip()


def _match_option_answer(answer: str, options: list[str]) -> str | None:
    normalized_answer = answer.casefold().strip()
    option_lookup = {option.casefold(): option for option in options}
    if normalized_answer in option_lookup:
        return option_lookup[normalized_answer]

    if normalized_answer.isdigit():
        index = int(normalized_answer) - 1
        if 0 <= index < len(options):
            return options[index]

    for index, option in enumerate(options):
        option_label = chr(ord("a") + index)
        if normalized_answer in {option_label, f"{option_label}.", f"{option_label})"}:
            return option

        option_prefix = option.split(maxsplit=1)[0].casefold().rstrip(".):")
        if normalized_answer == option_prefix:
            return option

    return None


def _normalize_candidates(raw_candidates: Any, options: list[str], n: int) -> list[dict[str, Any]]:
    if not isinstance(raw_candidates, list):
        return []

    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in raw_candidates:
        if not isinstance(item, dict):
            continue
        answer = str(item.get("answer", "")).strip()
        if not answer:
            continue

        if options:
            matched_answer = _match_option_answer(answer, options)
            if matched_answer is None:
                logger.info("Dropping top-N candidate not present in options: %r", answer)
                continue
            answer = matched_answer

        dedupe_key = answer.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        try:
            confidence = int(item.get("confidence", 50))
        except (TypeError, ValueError):
            confidence = 50

        candidates.append(
            {
                "rank": len(candidates) + 1,
                "answer": answer,
                "confidence": max(0, min(100, confidence)),
                "rationale": str(item.get("rationale", "")).strip(),
            }
        )
        if len(candidates) >= n:
            break

    return candidates


class TopNAssistance(AssistanceMethod):
    async def start(self, question: Question, params: dict) -> InteractionStep:
        settings = get_settings()
        model = params.get("model") or settings.llm.default_model
        requested_n = _clamp_top_n(params.get("n", _DEFAULT_TOP_N))
        options = _parse_options(question.options)
        n = min(requested_n, len(options)) if options else requested_n

        option_block = (
            "\n".join(f"{idx + 1}. {option}" for idx, option in enumerate(options))
            if options
            else "(free-response question; propose concise candidate answers)"
        )
        user_prompt = (
            f"Question:\n{question.question_text}\n\n"
            f"Question type: {question.question_type}\n"
            f"Options:\n{option_block}\n\n"
            f"Return exactly the top {n} candidate answer(s), ordered best first."
        )

        raw = await complete(
            [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            settings=settings.llm,
            response_format={"type": "json_object"},
            temperature=0,
        )

        try:
            parsed = json.loads(_strip_markdown_json(raw))
        except json.JSONDecodeError:
            logger.warning("Failed to parse top-N assistance response: %r", raw)
            parsed = {}

        candidates = _normalize_candidates(parsed.get("candidates"), options, n)
        if not candidates:
            return InteractionStep(type=StepType.NONE, is_terminal=True)

        return InteractionStep(
            type=StepType.DISPLAY,
            payload={
                "kind": "top_n",
                "top_n": n,
                "candidates": candidates,
                "has_options": bool(options),
            },
            is_terminal=True,
        )
