"""Source-independent learner error schema and taxonomy V1."""

from knowledge_core.normalization.error_taxonomy.ids import (
    make_error_instance_id,
    make_normalized_error_id,
    make_review_row_id,
    make_source_record_id,
)
from knowledge_core.normalization.error_taxonomy.models import (
    ErrorCorrection,
    ErrorInstance,
    LearnerCorpusSourceRecord,
    NormalizedErrorInstance,
    SourceNativeErrorLabel,
    TextSpan,
)
from knowledge_core.normalization.error_taxonomy.vocabulary import (
    ERROR_TAXONOMY_VERSION,
    NORMALIZED_ERROR_CATEGORIES,
)

__all__ = [
    "ERROR_TAXONOMY_VERSION",
    "NORMALIZED_ERROR_CATEGORIES",
    "ErrorCorrection",
    "ErrorInstance",
    "LearnerCorpusSourceRecord",
    "NormalizedErrorInstance",
    "SourceNativeErrorLabel",
    "TextSpan",
    "make_error_instance_id",
    "make_normalized_error_id",
    "make_review_row_id",
    "make_source_record_id",
]

