from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.models import GrammarRelationshipConfig
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy


DEFAULT_RELATIONSHIP_CONFIG_PATH = Path("config/grammar_relationship_rules.yaml")


class GrammarRelationshipConfigError(ValueError):
    """Raised when grammar relationship configuration cannot be loaded."""


def load_relationship_config(
    path: str | Path = DEFAULT_RELATIONSHIP_CONFIG_PATH,
) -> GrammarRelationshipConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise GrammarRelationshipConfigError(
            f"Grammar relationship config file not found: {config_path}",
        )

    try:
        raw_payload: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise GrammarRelationshipConfigError(
            f"Invalid YAML in {config_path}: {exc}",
        ) from exc

    if not isinstance(raw_payload, dict):
        raise GrammarRelationshipConfigError(
            f"Grammar relationship config must be a YAML mapping: {config_path}",
        )

    try:
        config = GrammarRelationshipConfig.model_validate(raw_payload)
    except ValidationError as exc:
        raise GrammarRelationshipConfigError(
            f"Invalid grammar relationship config {config_path}: {exc}",
        ) from exc

    taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
    unknown_ids = sorted(
        {
            skill_id
            for rule in config.curated_relationships
            for skill_id in [rule.source, rule.target]
            if skill_id not in taxonomy.all_node_ids
        },
    )
    if unknown_ids:
        joined = ", ".join(unknown_ids)
        raise GrammarRelationshipConfigError(
            f"relationship rule references unknown taxonomy node(s): {joined}",
        )
    return config

