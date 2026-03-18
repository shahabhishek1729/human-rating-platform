from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from models import ProlificStudyStatus


# Prolific schemas
class ProlificStudyConfig(BaseModel):
    description: str
    estimated_completion_time: int = Field(ge=1)
    reward: int = Field(ge=1)
    total_available_places: int = Field(ge=1)
    device_compatibility: list[Literal["desktop", "tablet", "mobile"]] = Field(
        default_factory=lambda: ["desktop"]
    )


# Experiment schemas
class ExperimentCreate(BaseModel):
    name: str
    num_ratings_per_question: int = 3
    prolific: ProlificStudyConfig


class ExperimentResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    num_ratings_per_question: int
    prolific_completion_url: Optional[str] = None
    prolific_study_id: Optional[str] = None
    prolific_study_status: Optional[ProlificStudyStatus] = None
    prolific_study_url: Optional[str] = None
    question_count: int = 0
    rating_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# Question schemas
class QuestionResponse(BaseModel):
    id: int
    question_id: str
    question_text: str
    options: Optional[str] = None
    question_type: str

    model_config = ConfigDict(from_attributes=True)


# Rater schemas
class RaterStartResponse(BaseModel):
    rater_id: int
    session_start: datetime
    session_end_time: datetime
    experiment_name: str
    completion_url: Optional[str] = None


class SessionStatusResponse(BaseModel):
    is_active: bool
    time_remaining_seconds: int
    questions_completed: int


# Rating schemas
class RatingSubmit(BaseModel):
    question_id: int
    answer: str
    confidence: int = Field(ge=1, le=5)
    time_started: datetime


class RatingResponse(BaseModel):
    id: int
    success: bool
