import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


REQUIRED_EXERCISE_FIELDS = {
    "exercise_code",
    "exercise_type",
    "topic_code",
    "subtopic",
    "level",
    "difficulty",
    "skill",
    "question_text",
    "options",
    "correct_answer",
    "explanation",
    "source",
}
REQUIRED_OPTION_FIELDS = {"label", "text", "is_correct"}
VALID_OPTION_LABELS = {"A", "B", "C", "D"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and import seed English exercises into SQLite."
    )
    parser.add_argument(
        "--input",
        default="./data/processed/seed_exercises.json",
        help="Path to seed_exercises.json.",
    )
    parser.add_argument(
        "--db",
        default=os.getenv("SQLITE_DB_PATH", "./data/sqlite/app.db"),
        help="SQLite database path.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append/upsert records instead of replacing the seed exercise bank.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the input file without writing to SQLite.",
    )
    return parser.parse_args()


def load_records(path: str | Path) -> list[dict[str, Any]]:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Seed exercise file not found: {input_path}")

    records = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("Seed exercise file must contain a JSON array.")
    validate_records(records)
    return records


def validate_records(records: list[dict[str, Any]]) -> None:
    seen_codes: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"Exercise at index {index} must be an object.")

        missing = REQUIRED_EXERCISE_FIELDS - set(record)
        if missing:
            code = record.get("exercise_code", f"index-{index}")
            raise ValueError(
                f"Exercise {code} missing fields: {', '.join(sorted(missing))}"
            )

        code = str(record["exercise_code"])
        if code in seen_codes:
            raise ValueError(f"Duplicate exercise_code: {code}")
        seen_codes.add(code)

        for field_name in [
            "exercise_code",
            "exercise_type",
            "topic_code",
            "subtopic",
            "level",
            "difficulty",
            "skill",
            "question_text",
            "correct_answer",
            "explanation",
            "source",
        ]:
            if not str(record[field_name]).strip():
                raise ValueError(f"Exercise {code} has empty field: {field_name}")

        options = record["options"]
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError(f"Exercise {code} must contain exactly 4 options.")

        labels: set[str] = set()
        correct_count = 0
        for option in options:
            if not isinstance(option, dict):
                raise ValueError(f"Exercise {code} option must be an object.")
            missing_option = REQUIRED_OPTION_FIELDS - set(option)
            if missing_option:
                raise ValueError(
                    f"Exercise {code} option missing fields: "
                    f"{', '.join(sorted(missing_option))}"
                )
            label = str(option["label"])
            if label not in VALID_OPTION_LABELS:
                raise ValueError(f"Exercise {code} has invalid option label: {label}")
            if label in labels:
                raise ValueError(f"Exercise {code} has duplicate option label: {label}")
            labels.add(label)
            if not str(option["text"]).strip():
                raise ValueError(f"Exercise {code} option {label} text is empty.")
            if bool(option["is_correct"]):
                correct_count += 1

        if correct_count != 1:
            raise ValueError(f"Exercise {code} must have exactly one correct option.")
        if record["correct_answer"] not in labels:
            raise ValueError(f"Exercise {code} correct_answer must match an option.")


def import_records(records: list[dict[str, Any]], db_path: str | Path, append: bool) -> None:
    target_path = Path(db_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(target_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        schema_path = ROOT_DIR / "app" / "persistence" / "schema.sql"
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        ensure_column(connection, "seed_exercises", "subtopic", "TEXT")
        ensure_column(connection, "seed_exercises", "error_tag", "TEXT")

        if not append:
            connection.execute("DELETE FROM seed_exercise_options")
            connection.execute("DELETE FROM seed_exercises")

        for record in records:
            upsert_seed_exercise(connection, record)

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def upsert_seed_exercise(
    connection: sqlite3.Connection,
    record: dict[str, Any],
) -> None:
    topic_id = ensure_topic(connection, record["topic_code"], record["skill"])
    existing = connection.execute(
        "SELECT id FROM seed_exercises WHERE exercise_code = ?",
        (record["exercise_code"],),
    ).fetchone()

    if existing is not None:
        connection.execute(
            "DELETE FROM seed_exercise_options WHERE exercise_id = ?",
            (int(existing["id"]),),
        )
        connection.execute(
            "DELETE FROM seed_exercises WHERE id = ?",
            (int(existing["id"]),),
        )

    cursor = connection.execute(
        """
        INSERT INTO seed_exercises (
            exercise_code,
            topic_id,
            subtopic,
            learner_level,
            difficulty,
            skill,
            exercise_type,
            question_text,
            correct_answer,
            explanation,
            error_tag,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["exercise_code"],
            topic_id,
            record["subtopic"],
            record["level"],
            record["difficulty"],
            record["skill"],
            record["exercise_type"],
            record["question_text"],
            record["correct_answer"],
            record["explanation"],
            record.get("error_tag"),
            record["source"],
        ),
    )
    exercise_id = int(cursor.lastrowid)

    for option in record["options"]:
        connection.execute(
            """
            INSERT INTO seed_exercise_options (
                exercise_id,
                option_label,
                option_text,
                is_correct
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                exercise_id,
                option["label"],
                option["text"],
                int(bool(option["is_correct"])),
            ),
        )


def ensure_topic(connection: sqlite3.Connection, topic_code: str, skill: str) -> int:
    connection.execute(
        """
        INSERT INTO topics (topic_code, name, skill)
        VALUES (?, ?, ?)
        ON CONFLICT(topic_code) DO NOTHING
        """,
        (topic_code, topic_code.replace("_", " ").title(), skill),
    )
    row = connection.execute(
        "SELECT id FROM topics WHERE topic_code = ?",
        (topic_code,),
    ).fetchone()
    return int(row["id"])


def ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    if column_name not in columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )


def print_summary(records: list[dict[str, Any]]) -> None:
    by_topic = Counter(record["topic_code"] for record in records)
    by_level = Counter(record["level"] for record in records)
    by_difficulty = Counter(record["difficulty"] for record in records)
    by_type = Counter(record["exercise_type"] for record in records)
    print(f"Validated {len(records)} seed exercises.")
    print(f"By topic: {dict(sorted(by_topic.items()))}")
    print(f"By level: {dict(sorted(by_level.items()))}")
    print(f"By difficulty: {dict(sorted(by_difficulty.items()))}")
    print(f"By type: {dict(sorted(by_type.items()))}")


def main() -> None:
    args = parse_args()
    records = load_records(args.input)
    print_summary(records)

    if args.validate_only:
        return

    import_records(records, args.db, append=args.append)
    print(f"Imported seed exercises into SQLite: {args.db}")


if __name__ == "__main__":
    main()
