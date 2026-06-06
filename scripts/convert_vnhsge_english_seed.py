"""Convert VNHSGE English JSON questions into project seed exercises.

The raw dataset contains duplicated English eval files under VNHSGE-E and
VNHSGE-V. This script intentionally reads one source folder, keeps only
text-only MCQ questions that fit the current English-practice scope, and writes
seed exercise records compatible with data/processed/seed_exercises.json.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any


DEFAULT_RAW_DIR = Path("data/raw/Dataset/VNHSGE-E/JSON format/eval/English")
DEFAULT_OUTPUT = Path("data/processed/seed_exercises_from_vnhsge.json")
DEFAULT_SEED_BANK = Path("data/processed/seed_exercises.json")
SOURCE_PREFIX = "vnhsge_english_eval"
GENERATED_CODE_PREFIX = "vnhsge_eng_"

OPTION_PATTERN = re.compile(
    r"(?ms)(?:^|\n)\s*A\.\s*(?P<A>.*?)(?:\n\s*B\.\s*)"
    r"(?P<B>.*?)(?:\n\s*C\.\s*)(?P<C>.*?)(?:\n\s*D\.\s*)"
    r"(?P<D>.*)$"
)
QUESTION_LABEL_PATTERN = re.compile(
    r"(?is)(?:Question|C[aâ]u)\s*\d+\s*[:.]?\s*"
)
SPACE_PATTERN = re.compile(r"[ \t\r\f\v]+")
ELLIPSIS_PATTERN = re.compile(r"\.{3,}|…+")
UNDERLINE_PATTERN = re.compile(r"\\underline\{([^{}]+)\}")


SUPPORTED_TOPICS = {
    "tenses",
    "passive_voice",
    "relative_clause",
    "conditional_sentence",
    "reported_speech",
    "prepositions",
    "vocabulary",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert VNHSGE English JSON files into seed exercises."
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=DEFAULT_RAW_DIR,
        help="Folder containing MET_Eng_IE_*.json files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Intermediate output path for converted records.",
    )
    parser.add_argument(
        "--seed-bank",
        type=Path,
        default=DEFAULT_SEED_BANK,
        help="Main seed_exercises.json path used when --merge is enabled.",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Append converted records into the main seed bank after removing old VNHSGE imports.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of converted records to write. 0 means no limit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    converted, stats = convert_folder(args.raw_dir)
    if args.limit > 0:
        converted = converted[: args.limit]

    write_json(args.output, converted)
    if args.merge:
        merge_into_seed_bank(args.seed_bank, converted)

    print(json.dumps({**stats, "written": len(converted)}, ensure_ascii=False, indent=2))
    print(f"Wrote intermediate seed file: {args.output}")
    if args.merge:
        print(f"Merged converted VNHSGE seeds into: {args.seed_bank}")


def convert_folder(raw_dir: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    stats = {
        "files": 0,
        "raw_records": 0,
        "duplicates": 0,
        "skipped_images": 0,
        "skipped_unparseable": 0,
        "skipped_out_of_scope": 0,
        "converted": 0,
    }

    for path in sorted(raw_dir.glob("MET_Eng_IE_*.json")):
        stats["files"] += 1
        raw_items = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw_items, list):
            raise ValueError(f"Expected a JSON array in {path}")

        for raw in raw_items:
            stats["raw_records"] += 1
            record_id = str(raw.get("ID") or "").strip()
            if not record_id or record_id in seen_ids:
                stats["duplicates"] += 1
                continue
            seen_ids.add(record_id)

            if raw.get("Image_Question") or raw.get("Image_Answer"):
                stats["skipped_images"] += 1
                continue

            parsed = parse_raw_record(raw)
            if parsed is None:
                stats["skipped_unparseable"] += 1
                continue

            topic_info = classify_record(parsed["question_text"], parsed["explanation"])
            if topic_info is None:
                stats["skipped_out_of_scope"] += 1
                continue

            topic_code, subtopic, skill, exercise_type, error_tag = topic_info
            if topic_code not in SUPPORTED_TOPICS:
                stats["skipped_out_of_scope"] += 1
                continue

            exercise_code = make_exercise_code(record_id)
            records.append(
                {
                    "exercise_code": exercise_code,
                    "exercise_type": exercise_type,
                    "topic_code": topic_code,
                    "subtopic": subtopic,
                    "level": "intermediate",
                    "difficulty": "medium",
                    "skill": skill,
                    "question_text": parsed["question_text"],
                    "options": parsed["options"],
                    "correct_answer": parsed["correct_answer"],
                    "explanation": parsed["explanation"],
                    "error_tag": error_tag,
                    "source": f"{SOURCE_PREFIX}:{record_id}",
                }
            )
            stats["converted"] += 1

    return records, stats


def parse_raw_record(raw: dict[str, Any]) -> dict[str, Any] | None:
    question = str(raw.get("Question") or "")
    correct_answer = str(raw.get("Choice") or "").strip().upper()
    explanation = clean_text(str(raw.get("Explanation") or ""))
    if correct_answer not in {"A", "B", "C", "D"} or not explanation:
        return None

    match = OPTION_PATTERN.search(question)
    if match is None:
        return None

    question_text = clean_question_stem(question[: match.start()])
    options = [
        {
            "label": label,
            "text": clean_option_text(match.group(label)),
            "is_correct": label == correct_answer,
        }
        for label in ["A", "B", "C", "D"]
    ]
    if not question_text or any(not option["text"] for option in options):
        return None

    return {
        "question_text": question_text,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": explanation,
    }


def classify_record(
    question_text: str,
    explanation: str,
) -> tuple[str, str, str, str, str] | None:
    text = normalize_for_matching(f"{question_text}\n{explanation}")

    if is_out_of_scope(text, question_text):
        return None

    if has_any(
        text,
        [
            "bi dong",
            "cau bi dong",
            "passive",
        ],
    ):
        return (
            "passive_voice",
            subtopic_for_passive(text),
            "grammar",
            "grammar_mcq",
            "active_passive_confusion",
        )

    if has_any(text, ["menh de quan he", "mdqh", "relative clause", "relative"]):
        return (
            "relative_clause",
            subtopic_for_relative(text),
            "grammar",
            "grammar_mcq",
            "relative_clause_form",
        )

    if has_any(text, ["gioi tu", "preposition", "keen + on", "interested in"]):
        return (
            "prepositions",
            subtopic_for_prepositions(text),
            "grammar",
            "grammar_mcq",
            "preposition_error",
        )

    if has_any(text, ["cau dieu kien", "conditional", "unless"]):
        return (
            "conditional_sentence",
            subtopic_for_conditionals(text),
            "grammar",
            "grammar_mcq",
            "wrong_condition_type",
        )

    if has_any(text, ["cau gian tiep", "gian tiep", "tuong thuat", "reported speech"]):
        return (
            "reported_speech",
            "reported_speech_general",
            "grammar",
            "grammar_mcq",
            "reported_speech_backshift",
        )

    if is_tense_related(text):
        return (
            "tenses",
            subtopic_for_tenses(text),
            "grammar",
            "grammar_mcq",
            "wrong_tense",
        )

    if is_vocabulary_related(text):
        return (
            "vocabulary",
            subtopic_for_vocabulary(text),
            "vocabulary",
            "vocabulary_mcq",
            "vocabulary_meaning_confusion",
        )

    return None


def is_out_of_scope(text: str, question_text: str) -> bool:
    if has_any(
        text,
        [
            "ngu am",
            "phat am",
            "trong am",
            "underlined part differs",
            "primary stress",
            "doc hieu",
            "tra loi cau hoi trong doan van",
            "tim thong tin chi tiet",
            "according to paragraph",
            "according to the passage",
            "paragraph",
            "mentioned in",
            "title for the passage",
            "which of the following is not true",
        ],
    ):
        return True
    question_lower = question_text.lower()
    if "read the following passage" in question_lower:
        return True
    if "following passage" in question_lower and len(question_text) > 500:
        return True
    if len(question_text) > 650:
        return True
    return False


def is_tense_related(text: str) -> bool:
    return has_any(
        text,
        [
            "thi cua dong tu",
            "su phoi hop thi",
            "thi qua khu",
            "qua khu don",
            "qua khu tiep dien",
            "qua khu hoan thanh",
            "hien tai don",
            "hien tai tiep dien",
            "hien tai hoan thanh",
            "tuong lai don",
            "future simple",
            "past simple",
            "past continuous",
            "present perfect",
            "when the teacher came",
            "last",
            "ago",
        ],
    )


def is_vocabulary_related(text: str) -> bool:
    return has_any(
        text,
        [
            "tu vung",
            "lua chon tu",
            "tu dong nghia",
            "tu trai nghia",
            "dong nghia",
            "trai nghia",
            "cum dong tu",
            "phrasal verb",
            "phrasal verbs",
            "collocation",
            "idiom",
            "thanh ngu",
            "tu loai",
            "word form",
            "word choice",
            "giao tiep",
            "communication",
            "closest in meaning",
            "opposite in meaning",
            "synonym",
            "antonym",
        ],
    )


def subtopic_for_passive(text: str) -> str:
    if has_any(text, ["modal", "khuyet thieu"]):
        return "modal_passive"
    if has_any(text, ["qua khu", "past"]):
        return "past_simple_passive"
    if has_any(text, ["tuong lai", "future"]):
        return "future_passive"
    return "passive_voice_general"


def subtopic_for_relative(text: str) -> str:
    if has_any(text, ["rut gon", "vp ii", "vpii", "participle"]):
        return "reduced_relative_clause"
    if "whose" in text:
        return "whose_for_possession"
    if "where" in text:
        return "where_for_places"
    if "which" in text:
        return "which_for_things"
    if "who" in text:
        return "who_for_people"
    return "relative_clause_general"


def subtopic_for_prepositions(text: str) -> str:
    if has_any(text, ["keen", "interested", "good at", "fond"]):
        return "dependent_prepositions"
    if has_any(text, ["time", "thoi gian"]):
        return "prepositions_of_time"
    if has_any(text, ["place", "noi chon"]):
        return "prepositions_of_place"
    return "prepositions_general"


def subtopic_for_conditionals(text: str) -> str:
    if "unless" in text:
        return "unless"
    if has_any(text, ["loai 1", "first conditional"]):
        return "first_conditional"
    if has_any(text, ["loai 2", "second conditional"]):
        return "second_conditional"
    if has_any(text, ["loai 3", "third conditional"]):
        return "third_conditional"
    return "conditional_sentence_general"


def subtopic_for_tenses(text: str) -> str:
    if has_any(text, ["qua khu tiep dien", "past continuous"]):
        return "past_continuous_interrupted_action"
    if has_any(text, ["qua khu hoan thanh", "past perfect"]):
        return "past_perfect_sequence"
    if has_any(text, ["hien tai hoan thanh", "present perfect"]):
        return "present_perfect_experience"
    if has_any(text, ["hien tai tiep dien", "present continuous"]):
        return "present_continuous_now"
    if has_any(text, ["qua khu don", "past simple", "last", "ago"]):
        return "past_simple_finished_time"
    if has_any(text, ["tuong lai", "future"]):
        return "future_will_prediction"
    if has_any(text, ["hien tai don", "present simple"]):
        return "present_simple_habits"
    return "tenses_general"


def subtopic_for_vocabulary(text: str) -> str:
    if has_any(text, ["cum dong tu", "phrasal"]):
        return "phrasal_verbs"
    if has_any(text, ["idiom", "thanh ngu"]):
        return "idioms"
    if "collocation" in text:
        return "collocations"
    if has_any(text, ["tu loai", "word form"]):
        return "word_forms"
    if has_any(text, ["dong nghia", "trai nghia", "synonym", "antonym"]):
        return "synonym_antonym"
    if has_any(text, ["giao tiep", "communication"]):
        return "communication_phrases"
    return "word_choice"


def clean_question_stem(raw_stem: str) -> str:
    stem = raw_stem.strip()
    matches = list(QUESTION_LABEL_PATTERN.finditer(stem))
    if matches:
        stem = stem[matches[-1].end() :]
    stem = UNDERLINE_PATTERN.sub(r"\1", stem)
    stem = stem.replace("\\", "")
    stem = ELLIPSIS_PATTERN.sub("____", stem)
    stem = re.sub(r"____\.+", "____", stem)
    return clean_text(stem)


def clean_option_text(raw_option: str) -> str:
    option = raw_option.strip()
    option = UNDERLINE_PATTERN.sub(r"\1", option)
    option = option.replace("\\", "")
    option = ELLIPSIS_PATTERN.sub("____", option)
    option = re.sub(r"____\.+", "____", option)
    return clean_text(option)


def clean_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = SPACE_PATTERN.sub(" ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_for_matching(text: str) -> str:
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.replace("đ", "d")
    text = SPACE_PATTERN.sub(" ", text)
    return text


def has_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def make_exercise_code(record_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", record_id).strip("_").lower()
    return f"{GENERATED_CODE_PREFIX}{normalized}"


def write_json(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def merge_into_seed_bank(seed_bank_path: Path, converted: list[dict[str, Any]]) -> None:
    existing = json.loads(seed_bank_path.read_text(encoding="utf-8"))
    if not isinstance(existing, list):
        raise ValueError(f"Expected a JSON array in {seed_bank_path}")

    kept = [
        record
        for record in existing
        if not str(record.get("exercise_code", "")).startswith(GENERATED_CODE_PREFIX)
    ]
    merged = [*kept, *converted]
    write_json(seed_bank_path, merged)


if __name__ == "__main__":
    main()
