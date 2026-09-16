from __future__ import annotations


class KnowledgeRepositoryError(RuntimeError):
    """Base exception for Knowledge Core repository failures."""


class KnowledgeNotFoundError(KnowledgeRepositoryError):
    """Raised when a requested Knowledge Core entity does not exist."""


class KnowledgeVersionNotFoundError(KnowledgeNotFoundError):
    """Raised when a requested knowledge version does not exist."""


class KnowledgeIntegrityError(KnowledgeRepositoryError):
    """Raised when persisted Knowledge Core rows violate repository assumptions."""
