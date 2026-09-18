from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from knowledge_core.sources.ud_ewt.models import UDSentenceRecord, UDTokenRecord
from knowledge_core.sources.ud_ewt.paths import RELEASED_SPLIT_FILENAMES, SOURCE_KEY


class UDEWTParseError(RuntimeError):
    """Raised when a CoNLL-U source cannot be parsed."""


def released_conllu_paths(root: str | Path) -> dict[str, Path]:
    root_path = Path(root)
    return {
        split: root_path / filename
        for split, filename in RELEASED_SPLIT_FILENAMES.items()
    }


def parse_release_files(root: str | Path) -> Iterator[UDSentenceRecord]:
    for split, path in released_conllu_paths(root).items():
        if not path.exists():
            raise UDEWTParseError(f"Released UD EWT file not found: {path}")
        yield from parse_conllu_file(path, split=split)


def parse_conllu_file(path: str | Path, *, split: str) -> Iterator[UDSentenceRecord]:
    source_path = Path(path)
    comments: dict[str, Any] = {}
    tokens: list[UDTokenRecord] = []
    sentence_number = 0

    with source_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\n")
            if not line:
                if comments or tokens:
                    sentence_number += 1
                    yield _build_sentence(
                        comments=comments,
                        tokens=tokens,
                        split=split,
                        source_path=source_path,
                        sentence_number=sentence_number,
                    )
                comments = {}
                tokens = []
                continue
            if line.startswith("#"):
                _add_comment(comments, line)
                continue
            columns = line.split("\t")
            if len(columns) != 10:
                raise UDEWTParseError(
                    f"Expected 10 CoNLL-U columns in {source_path} line {line_number}; got {len(columns)}",
                )
            token = _parse_token(
                columns,
                split=split,
                sentence_id=_sentence_id(comments, split, sentence_number + 1),
                source_line_number=line_number,
            )
            tokens.append(token)

    if comments or tokens:
        sentence_number += 1
        yield _build_sentence(
            comments=comments,
            tokens=tokens,
            split=split,
            source_path=source_path,
            sentence_number=sentence_number,
        )


def parse_feature_map(value: str) -> dict[str, list[str]]:
    if not value or value == "_":
        return {}
    features: dict[str, list[str]] = {}
    for item in value.split("|"):
        if not item:
            continue
        if "=" not in item:
            features.setdefault(item, []).append("true")
            continue
        key, raw_values = item.split("=", 1)
        values = [part for part in raw_values.split(",") if part]
        if key and values:
            features.setdefault(key, []).extend(values)
    return {key: sorted(set(values)) for key, values in sorted(features.items())}


def parse_deps(value: str) -> list[dict[str, str]]:
    if not value or value == "_":
        return []
    deps: list[dict[str, str]] = []
    for item in value.split("|"):
        if not item or ":" not in item:
            continue
        head, relation = item.split(":", 1)
        if head and relation:
            deps.append({"head": head, "relation": relation})
    return deps


def _add_comment(comments: dict[str, Any], line: str) -> None:
    text = line[1:].strip()
    if not text:
        return
    if "=" in text:
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip()
    else:
        key = text.strip()
        value = True
    existing = comments.get(key)
    if existing is None:
        comments[key] = value
    elif isinstance(existing, list):
        existing.append(value)
    else:
        comments[key] = [existing, value]


def _parse_token(
    columns: list[str],
    *,
    split: str,
    sentence_id: str,
    source_line_number: int,
) -> UDTokenRecord:
    token_id, form, lemma, upos, xpos, feats, head, deprel, deps, misc = columns
    return UDTokenRecord(
        token_ref=f"{SOURCE_KEY}:{split}:{sentence_id}:{token_id}",
        sentence_id=sentence_id,
        split=split,
        token_id=token_id,
        form=form,
        lemma=None if lemma == "_" else lemma,
        upos=None if upos == "_" else upos,
        xpos=None if xpos == "_" else xpos,
        feats=parse_feature_map(feats),
        feats_text=None if feats == "_" else feats,
        head=None if head == "_" else head,
        deprel=None if deprel == "_" else deprel,
        deps=parse_deps(deps),
        deps_text=None if deps == "_" else deps,
        misc=parse_feature_map(misc),
        misc_text=None if misc == "_" else misc,
        is_multiword="-" in token_id,
        is_empty_node="." in token_id,
        source_line_number=source_line_number,
    )


def _build_sentence(
    *,
    comments: dict[str, Any],
    tokens: list[UDTokenRecord],
    split: str,
    source_path: Path,
    sentence_number: int,
) -> UDSentenceRecord:
    sentence_id = _sentence_id(comments, split, sentence_number)
    fixed_tokens = [
        token.model_copy(
            update={
                "sentence_id": sentence_id,
                "token_ref": f"{SOURCE_KEY}:{split}:{sentence_id}:{token.token_id}",
            },
        )
        for token in tokens
    ]
    return UDSentenceRecord(
        sentence_id=sentence_id,
        split=split,
        text=_optional_string(comments.get("text")),
        newdoc_id=_optional_string(comments.get("newdoc id")),
        newpar_id=_optional_string(comments.get("newpar id")),
        metadata=dict(comments),
        tokens=fixed_tokens,
        source_file=str(source_path).replace("\\", "/"),
        source_sentence_number=sentence_number,
    )


def _sentence_id(comments: dict[str, Any], split: str, sentence_number: int) -> str:
    sent_id = _optional_string(comments.get("sent_id"))
    return sent_id or f"{split}-{sentence_number}"


def _optional_string(value: Any) -> str | None:
    if value is None or isinstance(value, list):
        return None
    text = str(value).strip()
    return text or None

