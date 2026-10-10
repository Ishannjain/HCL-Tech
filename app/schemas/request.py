from datetime import date, datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field
from app.config import get_settings

def today():
    return datetime.now(ZoneInfo(get_settings().timezone)).date()

class AskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: str = Field(min_length=1, max_length=5000)
    as_of_date: date = Field(default_factory=today)

class ReturnRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    order_id: str
    sku: str
    reason: str
    idempotency_key: str = Field(min_length=1, max_length=100)
