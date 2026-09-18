from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


ReviewerDecision = Literal["APPROVE", "REJECT", "NEEDS_REVIEW"]


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mapping_id: str
    reviewer_decision: ReviewerDecision
    reviewer_note: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""

    @field_validator("mapping_id")
    @classmethod
    def mapping_id_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("mapping_id is required")
        return value

    @model_validator(mode="after")
    def approval_has_auditor(self) -> ReviewDecision:
        if self.reviewer_decision in {"APPROVE", "REJECT"}:
            if not self.reviewed_by.strip() or not self.reviewed_at.strip():
                raise ValueError("APPROVE and REJECT require reviewed_by and reviewed_at")
        return self


class GroupDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_group_id: str
    reviewer_decision: ReviewerDecision
    reviewer_note: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""

    @model_validator(mode="after")
    def final_decision_has_auditor(self) -> GroupDecision:
        if self.reviewer_decision in {"APPROVE", "REJECT"}:
            if not self.reviewed_by.strip() or not self.reviewed_at.strip():
                raise ValueError("APPROVE and REJECT require reviewed_by and reviewed_at")
        return self
