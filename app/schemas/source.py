from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class SourceMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')
    doc_id: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_.-]+$')
    title: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    authority_level: int = Field(ge=1, le=5)
    doc_type: str
    version: str = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None
    supersedes: str = ''
    scope_categories: str = 'ALL'
    scope_tiers: str = 'ALL'
    provenance: str = Field(min_length=1)
    retrieved_on: date
    synthetic: str

    @field_validator('effective_to', mode='before')
    @classmethod
    def blank_date(cls, value):
        return None if value == '' else value

    @field_validator('synthetic')
    @classmethod
    def synthetic_flag(cls, value):
        if value not in {'Y','N'}:
            raise ValueError('synthetic must be Y or N')
        return value

    @field_validator('scope_categories','scope_tiers')
    @classmethod
    def normalized_scope(cls, value):
        return ';'.join(p.strip().upper() for p in value.split(';') if p.strip())

    @model_validator(mode='after')
    def dates_valid(self):
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError('effective_to precedes effective_from')
        if not self.scope_categories or not self.scope_tiers:
            raise ValueError('scope cannot be empty')
        return self

class RuleInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    rule_id: str = Field(min_length=1)
    description: str
    parameter: str
    operator: str = '='
    value: str
    scope_categories: str = 'ALL'
    scope_tiers: str = 'ALL'
    effective_from: date
    effective_to: date | None = None
    source_doc_id: str
    source_section: str
    conditions: dict = Field(default_factory=dict)
    evidence_quote: str = Field(min_length=1)

    @field_validator('effective_to', mode='before')
    @classmethod
    def blank_date(cls, value):
        return None if value == '' else value
