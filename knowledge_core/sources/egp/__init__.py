"""English Grammar Profile source ingestion adapter."""

from knowledge_core.sources.egp.config import load_egp_config
from knowledge_core.sources.egp.models import EGPCategoryConfig, EGPConfig, RawEGPRecord

__all__ = [
    "EGPCategoryConfig",
    "EGPConfig",
    "RawEGPRecord",
    "load_egp_config",
]
