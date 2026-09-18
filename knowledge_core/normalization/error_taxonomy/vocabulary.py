from __future__ import annotations

from typing import Literal


ERROR_TAXONOMY_VERSION = "error_taxonomy_v1"

NormalizedErrorCategory = Literal[
    "article",
    "determiner",
    "noun_number",
    "subject_verb_agreement",
    "verb_tense",
    "verb_form",
    "auxiliary",
    "modal",
    "preposition",
    "word_order",
    "pronoun",
    "adjective_adverb",
    "conjunction_clause",
    "negation",
    "passive_voice",
    "spelling",
    "punctuation",
    "lexical_choice",
    "word_form",
    "sentence_structure",
    "other",
    "unmapped",
]

NORMALIZED_ERROR_CATEGORIES: tuple[str, ...] = (
    "article",
    "determiner",
    "noun_number",
    "subject_verb_agreement",
    "verb_tense",
    "verb_form",
    "auxiliary",
    "modal",
    "preposition",
    "word_order",
    "pronoun",
    "adjective_adverb",
    "conjunction_clause",
    "negation",
    "passive_voice",
    "spelling",
    "punctuation",
    "lexical_choice",
    "word_form",
    "sentence_structure",
    "other",
    "unmapped",
)

NORMALIZED_ERROR_CATEGORY_DEFINITIONS: dict[str, str] = {
    "article": "Errors involving a, an, the, or zero article choice/use.",
    "determiner": "Errors involving determiners other than core article use.",
    "noun_number": "Errors involving singular/plural noun marking or countability.",
    "subject_verb_agreement": "Errors involving agreement between subject and finite verb.",
    "verb_tense": "Errors involving tense marking or tense choice.",
    "verb_form": "Errors involving infinitive, gerund, participle, or other verb form.",
    "auxiliary": "Errors involving auxiliary choice, omission, insertion, or placement.",
    "modal": "Errors involving modal auxiliary form or modal construction.",
    "preposition": "Errors involving preposition choice, omission, or insertion.",
    "word_order": "Errors involving constituent order or local word order.",
    "pronoun": "Errors involving pronoun form, case, reference, or choice.",
    "adjective_adverb": "Errors involving adjective/adverb form, order, or choice.",
    "conjunction_clause": "Errors involving conjunctions, subordination, or clause linking.",
    "negation": "Errors involving negative form, placement, or polarity marking.",
    "passive_voice": "Errors involving passive form or passive construction.",
    "spelling": "Source-marked spelling or orthographic word-form errors.",
    "punctuation": "Source-marked punctuation errors.",
    "lexical_choice": "Lexical choice errors not safely reducible to a grammar category.",
    "word_form": "Derivational or inflectional word-form errors not covered above.",
    "sentence_structure": "Broader sentence/clause structure errors.",
    "other": "Valid source label that does not fit the frozen V1 category set.",
    "unmapped": "Source label deliberately left unmapped pending review.",
}

VALID_NORMALIZED_ERROR_CATEGORY_SET = frozenset(NORMALIZED_ERROR_CATEGORIES)


def is_valid_error_category(category: str) -> bool:
    return category in VALID_NORMALIZED_ERROR_CATEGORY_SET

