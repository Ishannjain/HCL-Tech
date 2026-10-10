from datetime import date
from typing import Literal
from pydantic import BaseModel, Field

AnswerType = Literal['retrieved_fact','calculated','not_found','clarification_needed','refused','conflict_flagged']

class AskResponse(BaseModel):
    trace_id: str
    answer: str
    answer_type: AnswerType
    citations: list[dict] = Field(default_factory=list)
    tools_invoked: list[dict] = Field(default_factory=list)
    applied_rules: list[dict] = Field(default_factory=list)
    conflicts_detected: list[dict] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    explanation: str = ''
    as_of_date: date
