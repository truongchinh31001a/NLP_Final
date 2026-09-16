from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from knowledge_core.alignment.models import KnowledgeAlignmentConfig
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILL_SET


DEFAULT_ALIGNMENT_CONFIG_PATH = Path("config/knowledge_alignment_rules.yaml")


class KnowledgeAlignmentConfigError(ValueError):
    """Raised when knowledge alignment configuration cannot be loaded."""


def load_alignment_config(
    path: str | Path = DEFAULT_ALIGNMENT_CONFIG_PATH,
) -> KnowledgeAlignmentConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise KnowledgeAlignmentConfigError(
            f"Knowledge alignment config file not found: {config_path}",
        )

    try:
        raw_payload: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise KnowledgeAlignmentConfigError(
            f"Invalid YAML in {config_path}: {exc}",
        ) from exc

    if not isinstance(raw_payload, dict):
        raise KnowledgeAlignmentConfigError(
            f"Knowledge alignment config must be a YAML mapping: {config_path}",
        )

    try:
        config = KnowledgeAlignmentConfig.model_validate(raw_payload)
    except ValidationError as exc:
        raise KnowledgeAlignmentConfigError(
            f"Invalid knowledge alignment config {config_path}: {exc}",
        ) from exc

    unknown_rules = [
        rule.canonical_skill_id
        for rule in config.objective_alignment.rules
        if rule.canonical_skill_id not in CANONICAL_GRAMMAR_V1_SKILL_SET
    ]
    if unknown_rules:
        joined = ", ".join(sorted(unknown_rules))
        raise KnowledgeAlignmentConfigError(
            f"objective alignment rule references unknown Grammar V1 skill(s): {joined}",
        )
    return config

