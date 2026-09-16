from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from knowledge_core.alignment.cefr_alignment import (
    KnowledgeAlignmentDataset,
    build_knowledge_alignment,
)
from knowledge_core.alignment.config import (
    DEFAULT_ALIGNMENT_CONFIG_PATH,
    KnowledgeAlignmentConfigError,
    load_alignment_config,
)
from knowledge_core.alignment.models import KnowledgeAlignmentConfig
from knowledge_core.alignment.reporting import (
    AlignmentInputArtifacts,
    KnowledgeAlignmentOutputError,
    build_alignment_report,
    build_artifact_inspection_report,
    load_input_artifacts,
    write_alignment_outputs,
    write_alignment_report,
    write_review_csv,
)
from knowledge_core.alignment.validator import validate_alignment
from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS


logger = logging.getLogger(__name__)


def _add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    def default(value: object) -> object:
        return value if with_defaults else argparse.SUPPRESS

    parser.add_argument("--config", default=default(str(DEFAULT_ALIGNMENT_CONFIG_PATH)))
    parser.add_argument("--skill", default=default(None))
    parser.add_argument("--level", default=default(None))
    parser.add_argument("--min-confidence", type=float, default=default(0.0))
    parser.add_argument("--dry-run", action="store_true", default=default(False))
    parser.add_argument(
        "--log-level",
        default=default("INFO"),
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )


def build_parser() -> argparse.ArgumentParser:
    command_options = argparse.ArgumentParser(add_help=False)
    _add_common_arguments(command_options, with_defaults=False)

    parser = argparse.ArgumentParser(
        prog="python -m knowledge_core.alignment.cli",
        description="Align EGP and CEFR evidence around Grammar V1 skills.",
    )
    _add_common_arguments(parser, with_defaults=True)

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "inspect",
        parents=[command_options],
        help="Inspect canonical taxonomy and source artifacts",
    )
    subparsers.add_parser(
        "align",
        parents=[command_options],
        help="Generate knowledge alignment outputs",
    )
    subparsers.add_parser(
        "validate",
        parents=[command_options],
        help="Validate knowledge alignment outputs",
    )
    subparsers.add_parser(
        "report",
        parents=[command_options],
        help="Generate knowledge alignment report",
    )
    subparsers.add_parser(
        "run",
        parents=[command_options],
        help="Inspect, align, validate, write review CSV, and report",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(levelname)s %(name)s: %(message)s",
    )

    try:
        config = load_alignment_config(args.config)
        _validate_cli_filters(args)
        artifacts = load_input_artifacts(config)
        inspection = build_artifact_inspection_report(
            canonical_skills=CANONICAL_GRAMMAR_V1_SKILLS,
            artifacts=artifacts,
            config=config,
        )
        if args.command == "inspect":
            _print_inspection_summary(inspection)
            return 0

        dataset = _build_dataset(config, artifacts)
        validation = validate_alignment(
            canonical_skills=CANONICAL_GRAMMAR_V1_SKILLS,
            dataset=dataset,
            egp_records=artifacts.egp_records,
            egp_mappings=artifacts.egp_mappings,
            cefr_descriptors=artifacts.cefr_descriptors,
            cefr_objectives=artifacts.cefr_objectives,
        )

        if args.command == "align":
            if not args.dry_run:
                output_paths = write_alignment_outputs(dataset, config)
                review_path = write_review_csv(dataset.profiles, config)
                _print_output_paths(output_paths)
                logger.info("Wrote alignment review CSV: %s", review_path)
            _print_alignment_summary(dataset, args=args)
            return 0

        if args.command == "validate":
            _print_alignment_summary(dataset, args=args)
            _print_validation_summary(validation)
            return 1 if validation.error_count else 0

        if args.command == "report":
            report = build_alignment_report(
                canonical_skills=CANONICAL_GRAMMAR_V1_SKILLS,
                dataset=dataset,
                validation=validation,
                artifact_inspection=inspection,
            )
            if not args.dry_run:
                report_path = write_alignment_report(report, config)
                logger.info("Wrote alignment report: %s", report_path)
            _print_report_summary(report, args=args)
            return 1 if validation.error_count else 0

        if args.command == "run":
            report = build_alignment_report(
                canonical_skills=CANONICAL_GRAMMAR_V1_SKILLS,
                dataset=dataset,
                validation=validation,
                artifact_inspection=inspection,
            )
            if not args.dry_run:
                output_paths = write_alignment_outputs(dataset, config)
                review_path = write_review_csv(dataset.profiles, config)
                report_path = write_alignment_report(report, config)
                _print_output_paths(output_paths)
                logger.info("Wrote alignment review CSV: %s", review_path)
                logger.info("Wrote alignment report: %s", report_path)
            _print_report_summary(report, args=args)
            _print_validation_summary(validation)
            return 1 if validation.error_count else 0
    except (KnowledgeAlignmentConfigError, KnowledgeAlignmentOutputError, KeyError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


def _build_dataset(
    config: KnowledgeAlignmentConfig,
    artifacts: AlignmentInputArtifacts,
) -> KnowledgeAlignmentDataset:
    return build_knowledge_alignment(
        canonical_skills=CANONICAL_GRAMMAR_V1_SKILLS,
        egp_records=artifacts.egp_records,
        egp_mappings=artifacts.egp_mappings,
        cefr_descriptors=artifacts.cefr_descriptors,
        cefr_objectives=artifacts.cefr_objectives,
        config=config,
    )


def _validate_cli_filters(args: argparse.Namespace) -> None:
    if args.skill and args.skill not in CANONICAL_GRAMMAR_V1_SKILLS:
        raise KeyError(f"unknown Grammar V1 skill: {args.skill}")
    if args.min_confidence < 0.0 or args.min_confidence > 1.0:
        raise ValueError("--min-confidence must be between 0 and 1")


def _print_inspection_summary(report: dict[str, object]) -> None:
    taxonomy = report["canonical_taxonomy"]
    inputs = report["inputs"]
    logger.info("Canonical Grammar V1 skills: %s", taxonomy["skills"])
    logger.info("Canonical taxonomy hash: %s", taxonomy["hash"])
    for name, payload in inputs.items():
        logger.info("%s: %s records at %s", name, payload["records"], payload["path"])


def _print_alignment_summary(
    dataset: KnowledgeAlignmentDataset,
    *,
    args: argparse.Namespace,
) -> None:
    profiles = _filtered_profiles(dataset.profiles, args=args)
    logger.info("Grammar skill profiles: %s", len(dataset.profiles))
    logger.info("Displayed profiles after filters: %s", len(profiles))
    logger.info(
        "Profiles with EGP evidence: %s",
        sum(1 for profile in profiles if profile.egp_evidence_count > 0),
    )
    logger.info(
        "Profiles with CEFR primary level: %s",
        sum(1 for profile in profiles if profile.cefr_primary_level),
    )
    logger.info("Source evidence rows: %s", len(dataset.source_evidence))


def _print_report_summary(report: dict[str, object], *, args: argparse.Namespace) -> None:
    logger.info("Total canonical skills: %s", report["total_canonical_skills"])
    logger.info("Skills with EGP evidence: %s", report["skills_with_egp_evidence"])
    logger.info("Skills with CEFR alignment: %s", report["skills_with_cefr_alignment"])
    logger.info("Skills with direct objectives: %s", report["skills_with_direct_objectives"])
    logger.info(
        "Skills with contextual objectives: %s",
        report["skills_with_contextual_objectives"],
    )
    logger.info("Curated-only skills: %s", report["skills_curated_only"])
    logger.info(
        "Skills without CEFR alignment: %s",
        report["skills_without_cefr_alignment"],
    )
    logger.info(
        "Primary CEFR distribution: %s",
        report["distribution_by_primary_cefr_level"],
    )
    logger.info(
        "Alignment status distribution: %s",
        report["distribution_by_alignment_status"],
    )
    if args.skill:
        logger.info("Filtered skill requested: %s", args.skill)
    if args.min_confidence:
        logger.info("Minimum confidence display filter: %.2f", args.min_confidence)


def _print_validation_summary(validation: object) -> None:
    logger.info(
        "Alignment validation: %s error(s), %s warning(s)",
        validation.error_count,
        validation.warning_count,
    )


def _print_output_paths(paths: dict[str, object]) -> None:
    for name, path in paths.items():
        logger.info("Wrote %s: %s", name, path)


def _filtered_profiles(profiles: Sequence[object], *, args: argparse.Namespace) -> list[object]:
    filtered = list(profiles)
    if args.skill:
        filtered = [
            profile
            for profile in filtered
            if profile.canonical_skill_id == args.skill
        ]
    if args.level:
        filtered = [
            profile
            for profile in filtered
            if profile.cefr_primary_level == args.level
        ]
    if args.min_confidence:
        filtered = [
            profile
            for profile in filtered
            if profile.alignment_confidence >= args.min_confidence
        ]
    return filtered


if __name__ == "__main__":
    sys.exit(main())

