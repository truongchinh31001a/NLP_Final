from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from knowledge_core.sources.egp.models import EGPConfig


DEFAULT_CONFIG_PATH = Path("config/egp_categories.yaml")


class EGPConfigError(ValueError):
    """Raised when EGP source configuration cannot be loaded."""


def load_egp_config(path: str | Path = DEFAULT_CONFIG_PATH) -> EGPConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise EGPConfigError(f"EGP config file not found: {config_path}")

    try:
        raw_payload: Any = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise EGPConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(raw_payload, dict):
        raise EGPConfigError(f"EGP config must be a YAML mapping: {config_path}")

    try:
        return EGPConfig.model_validate(raw_payload)
    except ValidationError as exc:
        raise EGPConfigError(f"Invalid EGP config {config_path}: {exc}") from exc
