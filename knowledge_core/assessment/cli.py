from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from knowledge_core.assessment.builder import (
    BuiltAssessmentDataset,
    build_assessment_dataset,
)
from knowledge_core.assessment.config import (
    DEFAULT_ASSESSMENT_CONFIG_PATH,
    GrammarAssessmentConfigError,
    load_assessment_config,
)
from knowledge_core.assessment.models import (
    VALID_CRITERION_TYPES,
    GrammarAssessmentConfig,
)
from knowledge_core.assessment.reporting import (
    AssessmentOutputError,
    build_assessment_report,
    load_assessment_inputs,
    write_assessment_outputs,
    write_assessment_report,
    write_review_csv,
)
from knowledge_core.assessment.validator import validate_assessment_dataset
from knowledge_core.mapping.egp.canonical import (
    CANONICAL_GRAMMAR_V1_SKILL_SET,
    CANONICAL_GRAMMAR_V1_SKILLS,
)


logger = logging.getLogger(__name__)


def _add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    def default(value: object) -> object:
        return value if with_defaults else argparse.SUPPRESS

    parser.add_argument("--config", default=default(str(DEFAULT_ASSESSMENT_CONFIG_PATH)))
    parser.add_argument("--skill", default=default(None))
    parser.add_argument(
        "--criterion-type",
        choices=sorted(VALID_CRITERION_TYPES),
        default=default(None),
    )
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
        prog="python -m knowledge_core.assessment.cli",
        description="Build Grammar V1 assessment criteria.",
    )
    _add_common_arguments(parser, with_defaults=True)

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "inspect",
        parents=[command_options],
        help="Inspect assessment inputs",
    )
    subparsers.add_parser(
        "build",
        parents=[command_options],
        help="Build assessment artifacts",
    )
    subparsers.add_parser(
        "validate",
        parents=[command_options],
        help="Validate assessment criteria",
    )
    subparsers.add_parser(
        "report",
        parents=[command_options],
        help="Generate assessment report",
    )
    subparsers.add_parser(
        "run",
        parents=[command_options],
        help="Inspect, build, validate, review, and report",
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
        _validate_cli_filters(args)
        config = load_assessment_config(args.config)
        artifacts = load_assessment_inputs(config)

        if args.command == "inspect":
            _print_inspection(config, artifacts)
            return 0

        dataset = _build_dataset(config, artifacts)
        validation = validate_assessment_dataset(
            criteria=dataset.criteria,
            profiles=dataset.profiles,
            artifacts=artifacts,
        )
        report = build_assessment_report(
            criteria=dataset.criteria,
            profiles=dataset.profiles,
            validation=validation,
            config=config,
        )

        if args.command == "build":
            if not args.dry_run:
                output_paths = write_assessment_outputs(
                    criteria=dataset.criteria,
                    profiles=dataset.profiles,
                    config=config,
                )
                review_path = write_review_csv(dataset.criteria, config)
                _print_output_paths(output_paths)
                logger.info("Wrote assessment review CSV: %s", review_path)
            _print_dataset_summary(dataset, args=args)
            return 0

        if args.command == "validate":
            _print_dataset_summary(dataset, args=args)
            _print_validation(validation)
            return 1 if validation.error_count else 0

        if args.command == "report":
            if not args.dry_run:
                report_path = write_assessment_report(report, config)
                logger.info("Wrote assessment report: %s", report_path)
            _print_report_summary(report, args=args)
            return 1 if validation.error_count else 0

        if args.command == "run":
            if not args.dry_run:
                output_paths = write_assessment_outputs(
                    criteria=dataset.criteria,
                    profiles=dataset.profiles,
                    config=config,
                )
                review_path = write_review_csv(dataset.criteria, config)
                report_path = write_assessment_report(report, config)
                _print_output_paths(output_paths)
                logger.info("Wrote assessment review CSV: %s", review_path)
                logger.info("Wrote assessment report: %s", report_path)
            _print_report_summary(report, args=args)
            _print_validation(validation)
            return 1 if validation.error_count else 0
    except (
        AssessmentOutputError,
        GrammarAssessmentConfigError,
        KeyError,
        ValueError,
    ) as exc:
        logger.error("%s", exc)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


def _build_dataset(
    config: GrammarAssessmentConfig,
    artifacts,
) -> BuiltAssessmentDataset:
    return build_assessment_dataset(config=config, artifacts=artifacts)


def _validate_cli_filters(args: argparse.Namespace) -> None:
    if args.skill and args.skill not in CANONICAL_GRAMMAR_V1_SKILL_SET:
        raise KeyError(f"unknown Grammar V1 skill for --skill: {args.skill}")


def _print_inspection(config: GrammarAssessmentConfig, artifacts) -> None:
    grammatical_accuracy = [
        descriptor
        for descriptor in artifacts.cefr_descriptors
        if descriptor.scale_name == "grammatical_accuracy"
    ]
    logger.info("Canonical Grammar V1 atomic skills: %s", len(CANONICAL_GRAMMAR_V1_SKILLS))
    logger.info("Skill evidence profiles: %s at %s", len(artifacts.skill_profiles), config.inputs.skill_evidence_profiles)
    logger.info("CEFR-EGP alignment rows: %s at %s", len(artifacts.skill_alignments), config.inputs.cefr_egp_alignment)
    logger.info("CEFR descriptors: %s at %s", len(artifacts.cefr_descriptors), config.inputs.cefr_descriptors)
    logger.info("CEFR grammatical accuracy descriptors: %s", len(grammatical_accuracy))
    logger.info("EGP records: %s at %s", len(artifacts.egp_records), config.inputs.egp_records)
    logger.info("Relationship edges: %s at %s", len(artifacts.relationships), config.inputs.relationships)


def _print_dataset_summary(
    dataset: BuiltAssessmentDataset,
    *,
    args: argparse.Namespace,
) -> None:
    criteria = _filtered_criteria(dataset.criteria, args=args)
    logger.info("Total assessment criteria: %s", len(dataset.criteria))
    logger.info("Displayed criteria after filters: %s", len(criteria))
    logger.info("Assessment profiles: %s", len(dataset.profiles))
    counts: dict[str, int] = {}
    for criterion in criteria:
        counts[criterion.criterion_type] = counts.get(criterion.criterion_type, 0) + 1
    logger.info("Criteria by type: %s", counts)


def _print_report_summary(report: dict[str, object], *, args: argparse.Namespace) -> None:
    logger.info("Total canonical skills: %s", report["total_canonical_skills"])
    logger.info("Skills with assessment criteria: %s", report["skills_with_assessment_criteria"])
    logger.info("Total criteria: %s", report["total_criteria"])
    logger.info("Criteria by type: %s", report["criteria_by_type"])
    logger.info("Criteria by CEFR level: %s", report["criteria_by_cefr_level"])
    logger.info("Average criteria per skill: %s", report["average_criteria_per_skill"])
    logger.info("Task type distribution: %s", report["task_type_distribution"])
    logger.info("Skills without CEFR context: %s", report["skills_without_cefr_context"])
    logger.info("Criteria requiring review: %s", report["criteria_requiring_review_count"])
    logger.info("Validation errors: %s", report["validation_errors"])
    logger.info("Validation warnings: %s", report["validation_warnings"])
    logger.info("Taxonomy unchanged: %s", report["taxonomy_unchanged"])
    logger.info("Definition of Done satisfied: %s", report["definition_of_done_satisfied"])
    if args.skill:
        logger.info("Filtered skill requested: %s", args.skill)
    if args.criterion_type:
        logger.info("Filtered criterion type requested: %s", args.criterion_type)


def _print_validation(validation) -> None:
    logger.info(
        "Assessment validation: %s error(s), %s warning(s)",
        validation.error_count,
        validation.warning_count,
    )
    if validation.invalid_references:
        logger.error("Invalid references: %s", validation.invalid_references)
    if validation.duplicate_criteria:
        logger.error("Duplicate criteria: %s", validation.duplicate_criteria)
    if validation.missing_skill_ids:
        logger.error("Missing skill criteria: %s", validation.missing_skill_ids)


def _print_output_paths(paths: dict[str, object]) -> None:
    for name, path in paths.items():
        logger.info("Wrote %s: %s", name, path)


def _filtered_criteria(criteria, *, args: argparse.Namespace) -> list:
    filtered = list(criteria)
    if args.skill:
        filtered = [
            criterion
            for criterion in filtered
            if criterion.canonical_skill_id == args.skill
        ]
    if args.criterion_type:
        filtered = [
            criterion
            for criterion in filtered
            if criterion.criterion_type == args.criterion_type
        ]
    return filtered


if __name__ == "__main__":
    sys.exit(main())
