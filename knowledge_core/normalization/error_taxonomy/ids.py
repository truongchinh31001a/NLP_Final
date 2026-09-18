from __future__ import annotations

import hashlib
import json
import re
from typing import Any


_SAFE_ID_RE = re.compile(r"[^a-z0-9_]+")


def make_source_record_id(
    *,
    source_key: str,
    native_record_id: str,
    split: str | None = None,
) -> str:
    payload = {
        "native_record_id": native_record_id,
        "source_key": source_key,
        "split": split,
    }
    return _stable_prefixed_id("src", source_key, payload)


def make_error_instance_id(
    *,
    source_key: str,
    source_record_id: str,
    native_error_id: str | None = None,
    span_payload: dict[str, Any] | None = None,
    label_payload: dict[str, Any] | None = None,
) -> str:
    payload = {
        "label": label_payload or {},
        "native_error_id": native_error_id,
        "source_key": source_key,
        "source_record_id": source_record_id,
        "span": span_payload or {},
    }
    return _stable_prefixed_id("err", source_key, payload)


def make_normalized_error_id(
    *,
    error_instance_id: str,
    category: str,
    subtype: str | None = None,
) -> str:
    payload = {
        "category": category,
        "error_instance_id": error_instance_id,
        "subtype": subtype,
    }
    return _stable_prefixed_id("normerr", category, payload)


def make_review_row_id(
    *,
    review_queue: str,
    entity_id: str,
) -> str:
    payload = {
        "entity_id": entity_id,
        "review_queue": review_queue,
    }
    return _stable_prefixed_id("review", review_queue, payload)


def stable_hash(payload: Any, *, length: int = 16) -> str:
    encoded = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length]


def _stable_prefixed_id(prefix: str, namespace: str, payload: Any) -> str:
    safe_namespace = _safe_component(namespace)
    return f"{prefix}__{safe_namespace}__{stable_hash(payload)}"


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _safe_component(value: str) -> str:
    text = value.strip().casefold().replace("-", "_").replace(".", "_")
    text = _SAFE_ID_RE.sub("_", text).strip("_")
    return text or "unknown"

