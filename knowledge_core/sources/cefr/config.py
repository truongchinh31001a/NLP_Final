from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from knowledge_core.sources.cefr.models import CEFRConfig
from knowledge_core.sources.cefr.paths import DEFAULT_CONFIG_PATH


class CEFRConfigError(ValueError):
    """Raised when CEFR source configuration cannot be loaded."""


def load_cefr_config(path: str | Path = DEFAULT_CONFIG_PATH) -> CEFRConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise CEFRConfigError(f"CEFR config file not found: {config_path}")

    try:
        raw_payload: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CEFRConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw_payload, dict):
        raise CEFRConfigError(f"CEFR config must be a YAML mapping: {config_path}")

    try:
        return CEFRConfig.model_validate(raw_payload)
    except ValidationError as exc:
        raise CEFRConfigError(f"Invalid CEFR config {config_path}: {exc}") from exc

