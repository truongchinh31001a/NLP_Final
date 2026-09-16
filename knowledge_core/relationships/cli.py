from __future__ import annotations

import argparse
import logging
import sys
from typing import Sequence

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.relationships.builder import (
    BuiltRelationshipDataset,
    build_relationships,
)
from knowledge_core.relationships.config import (
    DEFAULT_RELATIONSHIP_CONFIG_PATH,
    GrammarRelationshipConfigError,
    load_relationship_config,
)
from knowledge_core.relationships.graph import SkillRelationshipGraph
from knowledge_core.relationships.models import VALID_RELATION_TYPES, GrammarRelationshipConfig
from knowledge_core.relationships.reporting import (
    RelationshipInputArtifacts,
    RelationshipOutputError,
    build_graph_export,
    build_relationship_report,
    load_relationship_inputs,
    write_graph_export,
    write_relationship_outputs,
    write_relationship_report,
    write_review_csv,
)
from knowledge_core.relationships.taxonomy import build_grammar_taxonomy
from knowledge_core.relationships.validator import validate_relationships


logger = logging.getLogger(__name__)


def _add_common_arguments(parser: argparse.ArgumentParser, *, with_defaults: bool) -> None:
    def default(value: object) -> object:
        return value if with_defaults else argparse.SUPPRESS

    parser.add_argument("--config", default=default(str(DEFAULT_RELATIONSHIP_CONFIG_PATH)))
    parser.add_argument("--skill", default=default(None))
    parser.add_argument("--relation", choices=sorted(VALID_RELATION_TYPES), default=default(None))
    parser.add_argument("--show-path", default=default(None))
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
        prog="python -m knowledge_core.relationships.cli",
        description="Build and validate Grammar V1 relationships.",
    )
    _add_common_arguments(parser, with_defaults=True)

    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "inspect",
        parents=[command_options],
        help="Inspect taxonomy and relationship inputs",
    )
    subparsers.add_parser(
        "build",
        parents=[command_options],
        help="Build relationship artifacts",
    )
    subparsers.add_parser(
        "validate",
        parents=[command_options],
        help="Validate relationship graph",
    )
    subparsers.add_parser(
        "analyze",
        parents=[command_options],
        help="Analyze graph utility outputs",
    )
    subparsers.add_parser(
        "report",
        parents=[command_options],
        help="Generate relationship report",
    )
    subparsers.add_parser(
        "run",
        parents=[command_options],
        help="Inspect, build, validate, analyze, review, and report",
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
        config = load_relationship_config(args.config)
        taxonomy = build_grammar_taxonomy(CANONICAL_GRAMMAR_V1_SKILLS)
        _validate_cli_filters(args, taxonomy)
        artifacts = load_relationship_inputs(config)
        if args.command == "inspect":
            _print_inspection(config, taxonomy, artifacts)
            return 0

        dataset = _build_dataset(config, taxonomy, artifacts)
        graph = SkillRelationshipGraph(dataset.relationships, taxonomy)
        analysis = graph.analyze()
        validation = validate_relationships(dataset.relationships, taxonomy)
        report = build_relationship_report(
            relationships=dataset.relationships,
            taxonomy=taxonomy,
            analysis=analysis,
            validation=validation,
            config=config,
        )
        graph_export = build_graph_export(
            relationships=dataset.relationships,
            taxonomy=taxonomy,
            analysis=analysis,
        )

        if args.command == "build":
            if not args.dry_run:
                output_paths = write_relationship_outputs(dataset.relationships, config)
                review_path = write_review_csv(dataset.relationships, config)
                _print_output_paths(output_paths)
                logger.info("Wrote relationship review CSV: %s", review_path)
            _print_relationship_summary(dataset.relationships, args=args)
            return 0

        if args.command == "validate":
            _print_relationship_summary(dataset.relationships, args=args)
            _print_validation(validation)
            _print_optional_path(graph, args)
            return 1 if validation.error_count else 0

        if args.command == "analyze":
            _print_analysis(analysis, args=args)
            _print_optional_path(graph, args)
            return 1 if validation.error_count else 0

        if args.command == "report":
            if not args.dry_run:
                report_path = write_relationship_report(report, config)
                graph_path = write_graph_export(graph_export, config)
                logger.info("Wrote relationship report: %s", report_path)
                logger.info("Wrote relationship graph export: %s", graph_path)
            _print_report_summary(report, args=args)
            _print_optional_path(graph, args)
            return 1 if validation.error_count else 0

        if args.command == "run":
            if not args.dry_run:
                output_paths = write_relationship_outputs(dataset.relationships, config)
                review_path = write_review_csv(dataset.relationships, config)
                report_path = write_relationship_report(report, config)
                graph_path = write_graph_export(graph_export, config)
                _print_output_paths(output_paths)
                logger.info("Wrote relationship review CSV: %s", review_path)
                logger.info("Wrote relationship report: %s", report_path)
                logger.info("Wrote relationship graph export: %s", graph_path)
            _print_report_summary(report, args=args)
            _print_validation(validation)
            _print_optional_path(graph, args)
            return 1 if validation.error_count else 0
    except (GrammarRelationshipConfigError, RelationshipOutputError, KeyError, ValueError) as exc:
        logger.error("%s", exc)
        return 1

    parser.error(f"unsupported command: {args.command}")
    return 2


def _build_dataset(
    config: GrammarRelationshipConfig,
    taxonomy: object,
    artifacts: RelationshipInputArtifacts,
) -> BuiltRelationshipDataset:
    return build_relationships(
        taxonomy=taxonomy,
        config=config,
        skill_profiles=artifacts.skill_profiles,
        skill_alignments=artifacts.skill_alignments,
    )


def _validate_cli_filters(args: argparse.Namespace, taxonomy: object) -> None:
    for option_name in ["skill", "show_path"]:
        value = getattr(args, option_name, None)
        if value and value not in taxonomy.all_node_ids:
            raise KeyError(f"unknown Grammar V1 taxonomy node for --{option_name.replace('_', '-')}: {value}")


def _print_inspection(
    config: GrammarRelationshipConfig,
    taxonomy: object,
    artifacts: RelationshipInputArtifacts,
) -> None:
    logger.info("Canonical Grammar V1 atomic skills: %s", len(taxonomy.atomic_skill_ids))
    logger.info("Taxonomy group nodes: %s", len(taxonomy.group_node_ids))
    logger.info("Taxonomy root: %s", taxonomy.root_id)
    logger.info("Taxonomy hash: %s", taxonomy.taxonomy_hash)
    logger.info("Skill evidence profiles: %s at %s", len(artifacts.skill_profiles), config.inputs.skill_evidence_profiles)
    logger.info("CEFR-EGP alignment rows: %s at %s", len(artifacts.skill_alignments), config.inputs.cefr_egp_alignment)
    logger.info("Curated relationship rules: %s", len(config.curated_relationships))


def _print_relationship_summary(
    relationships: Sequence[object],
    *,
    args: argparse.Namespace,
) -> None:
    filtered = _filtered_relationships(relationships, args=args)
    logger.info("Total relationships: %s", len(relationships))
    logger.info("Displayed relationships after filters: %s", len(filtered))
    counts: dict[str, int] = {}
    for relationship in filtered:
        counts[relationship.relation_type] = counts.get(relationship.relation_type, 0) + 1
    logger.info("Relationships by type: %s", counts)


def _print_report_summary(report: dict[str, object], *, args: argparse.Namespace) -> None:
    logger.info("Total relationships: %s", report["total_relationships"])
    logger.info("Relationships by type: %s", report["relationships_by_type"])
    logger.info("Hard prerequisites: %s", report["hard_prerequisite_count"])
    logger.info("Soft prerequisites: %s", report["soft_prerequisite_count"])
    logger.info("Bidirectional relationships: %s", report["bidirectional_relationship_count"])
    logger.info("Canonical skills covered: %s", report["canonical_skills_covered"])
    logger.info("Isolated skills: %s", report["isolated_skills"])
    logger.info("Root prerequisite skills: %s", report["root_prerequisite_skills"])
    logger.info("Terminal skills: %s", report["terminal_skills"])
    logger.info("DAG valid: %s", report["prerequisite_dag_valid"])
    logger.info("Max prerequisite depth: %s", report["max_prerequisite_depth"])
    logger.info("Longest prerequisite path: %s", report["longest_prerequisite_path"])
    logger.info("Relationships requiring review: %s", report["relationships_requiring_review_count"])
    if args.skill:
        logger.info("Filtered skill requested: %s", args.skill)
    if args.relation:
        logger.info("Filtered relation requested: %s", args.relation)


def _print_analysis(analysis: object, *, args: argparse.Namespace) -> None:
    logger.info("Total nodes: %s", analysis.total_nodes)
    logger.info("Total atomic skills: %s", analysis.total_atomic_skills)
    logger.info("Max prerequisite depth: %s", analysis.max_prerequisite_depth)
    logger.info("Longest prerequisite path: %s", analysis.longest_prerequisite_path)
    logger.info("Connected components: %s", len(analysis.connected_components))
    if args.skill:
        summary = analysis.node_summaries.get(args.skill)
        logger.info("Node summary for %s: %s", args.skill, summary.model_dump(mode="json") if summary else None)


def _print_validation(validation: object) -> None:
    logger.info(
        "Relationship validation: %s error(s), %s warning(s)",
        validation.error_count,
        validation.warning_count,
    )
    logger.info("Prerequisite DAG valid: %s", validation.prerequisite_dag_valid)
    if validation.cycles_found:
        logger.error("Prerequisite cycles: %s", validation.cycles_found)


def _print_optional_path(graph: SkillRelationshipGraph, args: argparse.Namespace) -> None:
    if args.show_path:
        logger.info(
            "Learning path to %s: %s",
            args.show_path,
            graph.get_learning_path(args.show_path),
        )


def _print_output_paths(paths: dict[str, object]) -> None:
    for name, path in paths.items():
        logger.info("Wrote %s: %s", name, path)


def _filtered_relationships(
    relationships: Sequence[object],
    *,
    args: argparse.Namespace,
) -> list[object]:
    filtered = list(relationships)
    if args.skill:
        filtered = [
            relationship
            for relationship in filtered
            if relationship.source_skill_id == args.skill
            or relationship.target_skill_id == args.skill
        ]
    if args.relation:
        filtered = [
            relationship
            for relationship in filtered
            if relationship.relation_type == args.relation
        ]
    return filtered


if __name__ == "__main__":
    sys.exit(main())

