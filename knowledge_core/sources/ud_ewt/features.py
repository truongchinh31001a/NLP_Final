from __future__ import annotations

from collections import defaultdict
from typing import Any

from knowledge_core.sources.ud_ewt.models import UDSentenceRecord, UDTokenRecord


BE_LEMMAS = {"be"}
HAVE_LEMMAS = {"have"}
DO_LEMMAS = {"do"}
MODAL_LEMMAS = {"can", "could", "must", "should"}
ARTICLE_LEMMAS = {"a", "an", "the"}


def syntactic_tokens(sentence: UDSentenceRecord) -> list[UDTokenRecord]:
    return [
        token
        for token in sentence.tokens
        if not token.is_multiword and not token.is_empty_node
    ]


def token_by_id(sentence: UDSentenceRecord) -> dict[str, UDTokenRecord]:
    return {
        token.token_id: token
        for token in sentence.tokens
        if not token.is_multiword
    }


def extract_morphological_signature(token: UDTokenRecord) -> dict[str, Any]:
    return {
        "upos": token.upos,
        "xpos": token.xpos,
        "feats": token.feats,
        "lemma": token.lemma,
    }


def extract_dependency_signature(sentence: UDSentenceRecord) -> list[dict[str, str | bool]]:
    signatures: list[dict[str, str | bool]] = []
    for token in sentence.tokens:
        if token.is_multiword:
            continue
        if token.head and token.deprel:
            signatures.append(
                {
                    "head": token.head,
                    "dependent": token.token_id,
                    "relation": token.deprel,
                    "enhanced": False,
                },
            )
        for dep in token.deps:
            signatures.append(
                {
                    "head": dep["head"],
                    "dependent": token.token_id,
                    "relation": dep["relation"],
                    "enhanced": True,
                },
            )
    return signatures


def find_subject_verb_pairs(sentence: UDSentenceRecord) -> list[tuple[UDTokenRecord, UDTokenRecord]]:
    tokens = token_by_id(sentence)
    pairs: list[tuple[UDTokenRecord, UDTokenRecord]] = []
    for token in syntactic_tokens(sentence):
        if token.deprel not in {"nsubj", "nsubj:pass", "csubj", "csubj:pass"}:
            continue
        if not token.head:
            continue
        head = tokens.get(token.head)
        if head and head.upos in {"VERB", "AUX"}:
            pairs.append((token, head))
    return pairs


def find_auxiliary_chains(sentence: UDSentenceRecord) -> list[dict[str, Any]]:
    tokens = token_by_id(sentence)
    auxiliaries: dict[str, list[UDTokenRecord]] = defaultdict(list)
    for token in syntactic_tokens(sentence):
        if token.deprel in {"aux", "aux:pass", "cop"} and token.head:
            auxiliaries[token.head].append(token)
    chains: list[dict[str, Any]] = []
    for head_id, aux_tokens in auxiliaries.items():
        head = tokens.get(head_id)
        if head:
            chains.append({"head": head, "auxiliaries": sorted(aux_tokens, key=_token_sort_key)})
    return chains


def find_determiner_noun_pairs(sentence: UDSentenceRecord) -> list[tuple[UDTokenRecord, UDTokenRecord]]:
    tokens = token_by_id(sentence)
    pairs: list[tuple[UDTokenRecord, UDTokenRecord]] = []
    for token in syntactic_tokens(sentence):
        if token.deprel != "det" or not token.head:
            continue
        head = tokens.get(token.head)
        if head and head.upos in {"NOUN", "PROPN", "PRON"}:
            pairs.append((token, head))
    return pairs


def find_passive_structures(sentence: UDSentenceRecord) -> list[dict[str, Any]]:
    tokens = token_by_id(sentence)
    structures: list[dict[str, Any]] = []
    for token in syntactic_tokens(sentence):
        if token.deprel in {"aux:pass", "nsubj:pass", "csubj:pass"} and token.head:
            head = tokens.get(token.head)
            if head:
                structures.append({"head": head, "marker": token, "relation": token.deprel})
        if "Pass" in token.feats.get("Voice", []):
            structures.append({"head": token, "marker": token, "relation": "Voice=Pass"})
    return structures


def is_third_person_singular_subject(token: UDTokenRecord) -> bool:
    person = set(token.feats.get("Person", []))
    number = set(token.feats.get("Number", []))
    if "3" in person and "Sing" in number:
        return True
    if token.lemma in {"he", "she", "it", "this", "that"}:
        return True
    return False


def is_present_finite_verb(token: UDTokenRecord) -> bool:
    return (
        token.upos in {"VERB", "AUX"}
        and "Pres" in token.feats.get("Tense", [])
        and "Fin" in token.feats.get("VerbForm", [])
    )


def has_subject_verb_agreement_pattern(sentence: UDSentenceRecord) -> bool:
    return any(
        is_third_person_singular_subject(subject) and is_present_finite_verb(verb)
        for subject, verb in find_subject_verb_pairs(sentence)
    )


def has_present_perfect_structure(sentence: UDSentenceRecord) -> bool:
    for chain in find_auxiliary_chains(sentence):
        head = chain["head"]
        if not is_past_participle(head):
            continue
        if any(_lemma(aux) in HAVE_LEMMAS and "Pres" in aux.feats.get("Tense", []) for aux in chain["auxiliaries"]):
            return True
    return False


def has_progressive_structure(sentence: UDSentenceRecord, *, tense: str | None = None) -> bool:
    for chain in find_auxiliary_chains(sentence):
        head = chain["head"]
        if not is_present_participle(head):
            continue
        be_aux = [
            aux
            for aux in chain["auxiliaries"]
            if _lemma(aux) in BE_LEMMAS and (tense is None or tense in aux.feats.get("Tense", []))
        ]
        if be_aux:
            return True
    return False


def has_passive_structure(sentence: UDSentenceRecord) -> bool:
    return bool(find_passive_structures(sentence))


def has_passive_structure_with_tense(sentence: UDSentenceRecord, *, tense: str) -> bool:
    for chain in find_auxiliary_chains(sentence):
        if any(aux.deprel == "aux:pass" and tense in aux.feats.get("Tense", []) for aux in chain["auxiliaries"]):
            return True
    return False


def has_agent_by_structure(sentence: UDSentenceRecord) -> bool:
    tokens = token_by_id(sentence)
    for token in syntactic_tokens(sentence):
        if token.deprel == "obl:agent":
            return True
        if _lemma(token) == "by" and token.deprel == "case" and token.head:
            head = tokens.get(token.head)
            if head and head.deprel == "obl:agent":
                return True
    return False


def has_modal_auxiliary(sentence: UDSentenceRecord, lemma: str | None = None) -> bool:
    lemmas = {lemma} if lemma else MODAL_LEMMAS
    return any(
        token.deprel == "aux"
        and (token.xpos == "MD" or token.upos == "AUX")
        and _lemma(token) in lemmas
        for token in syntactic_tokens(sentence)
    )


def has_article_noun_structure(sentence: UDSentenceRecord, *, article: str | None = None) -> bool:
    articles = {article} if article else ARTICLE_LEMMAS
    return any(_lemma(det) in articles for det, _noun in find_determiner_noun_pairs(sentence))


def has_present_simple_negative(sentence: UDSentenceRecord) -> bool:
    has_do_aux = any(
        token.deprel == "aux" and _lemma(token) in DO_LEMMAS and "Pres" in token.feats.get("Tense", [])
        for token in syntactic_tokens(sentence)
    )
    has_neg = any(
        token.deprel == "advmod" and (_lemma(token) == "not" or "Neg" in token.feats.get("Polarity", []))
        for token in syntactic_tokens(sentence)
    )
    return has_do_aux and has_neg


def has_present_simple_question(sentence: UDSentenceRecord) -> bool:
    text = sentence.text or ""
    if not text.strip().endswith("?"):
        return False
    return any(
        token.deprel == "aux" and _lemma(token) in DO_LEMMAS and "Pres" in token.feats.get("Tense", [])
        for token in syntactic_tokens(sentence)
    )


def is_past_participle(token: UDTokenRecord) -> bool:
    return (
        "Part" in token.feats.get("VerbForm", [])
        and ("Past" in token.feats.get("Tense", []) or token.xpos == "VBN")
    )


def is_present_participle(token: UDTokenRecord) -> bool:
    return (
        "Part" in token.feats.get("VerbForm", [])
        and ("Pres" in token.feats.get("Tense", []) or token.xpos == "VBG")
    )


def _lemma(token: UDTokenRecord) -> str:
    return (token.lemma or token.form).casefold()


def _token_sort_key(token: UDTokenRecord) -> tuple[int, str]:
    try:
        return (int(token.token_id), token.token_id)
    except ValueError:
        return (10**9, token.token_id)

