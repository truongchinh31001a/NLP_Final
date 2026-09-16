from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from knowledge_core.assessment.models import GrammarAssessmentConfig


DEFAULT_ASSESSMENT_CONFIG_PATH = Path("config/grammar_assessment_rules.yaml")


class GrammarAssessmentConfigError(ValueError):
    """Raised when grammar assessment configuration cannot be loaded."""


def load_assessment_config(
    path: str | Path = DEFAULT_ASSESSMENT_CONFIG_PATH,
) -> GrammarAssessmentConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise GrammarAssessmentConfigError(
            f"Grammar assessment config file not found: {config_path}",
        )

    try:
        raw_payload: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise GrammarAssessmentConfigError(
            f"Invalid YAML in {config_path}: {exc}",
        ) from exc

    if not isinstance(raw_payload, dict):
        raise GrammarAssessmentConfigError(
            f"Grammar assessment config must be a YAML mapping: {config_path}",
        )

    try:
        return GrammarAssessmentConfig.model_validate(raw_payload)
    except ValidationError as exc:
        raise GrammarAssessmentConfigError(
            f"Invalid grammar assessment config {config_path}: {exc}",
        ) from exc
