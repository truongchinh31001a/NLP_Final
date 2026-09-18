from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class MisconceptionReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    misconception_id: str
    reviewer_decision: Literal["APPROVE", "REJECT", "NEEDS_REVIEW"]
    reviewer_note: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""

    @field_validator("misconception_id")
    @classmethod
    def require_id(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("misconception_id is required")
        return value

    @model_validator(mode="after")
    def approval_has_auditor(self) -> MisconceptionReviewDecision:
        if self.reviewer_decision in {"APPROVE", "REJECT"}:
            if not self.reviewed_by.strip() or not self.reviewed_at.strip():
                raise ValueError("APPROVE and REJECT require reviewed_by and reviewed_at")
        return self
