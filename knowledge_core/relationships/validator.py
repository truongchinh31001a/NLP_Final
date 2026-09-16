from __future__ import annotations

from collections import defaultdict, deque
from typing import Sequence

from knowledge_core.relationships.builder import (
    inverse_relationship_key,
    relationship_key,
)
from knowledge_core.relationships.graph import SkillRelationshipGraph
from knowledge_core.relationships.models import (
    VALID_DEPENDENCY_STRENGTHS,
    VALID_RELATION_TYPES,
    RelationshipValidationIssue,
    RelationshipValidationResult,
    SkillRelationship,
    dependency_strength_for_relation,
    is_bidirectional_relation,
)
from knowledge_core.relationships.taxonomy import GrammarTaxonomy, is_immediate_parent


def validate_relationships(
    relationships: Sequence[SkillRelationship],
    taxonomy: GrammarTaxonomy,
) -> RelationshipValidationResult:
    issues: list[RelationshipValidationIssue] = []
    duplicate_edges: list[str] = []
    invalid_references: set[str] = set()

    edge_groups: dict[tuple[str, str, str], list[SkillRelationship]] = defaultdict(list)
    directed_groups: dict[tuple[str, str, str], list[SkillRelationship]] = defaultdict(list)
    relationship_id_groups: dict[str, list[SkillRelationship]] = defaultdict(list)

    for relationship in relationships:
        relationship_id_groups[relationship.relationship_id].append(relationship)
        key = relationship_key(relationship)
        edge_groups[key].append(relationship)
        directed_groups[
            (
                relationship.source_skill_id,
                relationship.target_skill_id,
                relationship.relation_type,
            )
        ].append(relationship)

        context = _relationship_context(relationship)
        if relationship.source_skill_id == relationship.target_skill_id:
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="self_loop",
                    message="Relationship source and target must differ",
                    **context,
                ),
            )
        for node_id in [relationship.source_skill_id, relationship.target_skill_id]:
            if node_id not in taxonomy.all_node_ids:
                invalid_references.add(node_id)
                issues.append(
                    RelationshipValidationIssue(
                        severity="error",
                        code="unknown_skill_id",
                        message=f"Relationship references unknown taxonomy node: {node_id}",
                        **context,
                    ),
                )
        if relationship.relation_type not in VALID_RELATION_TYPES:
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="invalid_relation_type",
                    message=f"Invalid relation type: {relationship.relation_type}",
                    **context,
                ),
            )
        expected_strength = dependency_strength_for_relation(
            relationship.relation_type,
        )
        if relationship.dependency_strength not in VALID_DEPENDENCY_STRENGTHS:
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="invalid_dependency_strength",
                    message=(
                        f"Invalid dependency strength: "
                        f"{relationship.dependency_strength}"
                    ),
                    **context,
                ),
            )
        elif relationship.dependency_strength != expected_strength:
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="dependency_strength_mismatch",
                    message=(
                        "dependency_strength must match relation semantics: "
                        f"{relationship.relation_type} -> {expected_strength}"
                    ),
                    **context,
                ),
            )
        if relationship.bidirectional != is_bidirectional_relation(relationship.relation_type):
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="bidirectional_flag_mismatch",
                    message="bidirectional flag must match relation type convention",
                    **context,
                ),
            )
        if relationship.relation_type == "parent_of" and not is_immediate_parent(
            relationship.source_skill_id,
            relationship.target_skill_id,
        ):
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="invalid_structural_parent",
                    message="parent_of must connect an immediate taxonomy parent to its child",
                    **context,
                ),
            )
        if not relationship.evidence:
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="missing_relationship_evidence",
                    message="Every relationship must include provenance evidence",
                    **context,
                ),
            )

    for relationship_id, grouped in relationship_id_groups.items():
        if len(grouped) < 2:
            continue
        for relationship in grouped:
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="duplicate_relationship_id",
                    message=f"relationship_id {relationship_id!r} appears {len(grouped)} times",
                    **_relationship_context(relationship),
                ),
            )

    for key, grouped in edge_groups.items():
        if len(grouped) < 2:
            continue
        duplicate_edges.append("|".join(key))
        for relationship in grouped:
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="duplicate_edge",
                    message=f"Duplicate edge appears {len(grouped)} times",
                    **_relationship_context(relationship),
                ),
            )

    for relationship in relationships:
        if not relationship.bidirectional:
            continue
        inverse_key = inverse_relationship_key(relationship)
        if inverse_key in directed_groups:
            duplicate_edges.append("|".join(relationship_key(relationship)))
            issues.append(
                RelationshipValidationIssue(
                    severity="error",
                    code="duplicate_inverse_bidirectional_edge",
                    message="Bidirectional relationships must not also appear as mirrored edges",
                    **_relationship_context(relationship),
                ),
            )

    graph = SkillRelationshipGraph(list(relationships), taxonomy)
    cycles = graph.find_prerequisite_cycles()
    for cycle in cycles:
        issues.append(
            RelationshipValidationIssue(
                severity="error",
                code="prerequisite_cycle",
                message="prerequisite_of graph must be acyclic: " + " -> ".join(cycle),
            ),
        )

    unreachable = _unreachable_atomic_skills(relationships, taxonomy)
    for skill_id in unreachable:
        issues.append(
            RelationshipValidationIssue(
                severity="error",
                code="taxonomy_leaf_unreachable",
                message="Atomic skill is not reachable from taxonomy root through parent_of edges",
                source_skill_id=taxonomy.root_id,
                target_skill_id=skill_id,
                relation_type="parent_of",
            ),
        )

    return RelationshipValidationResult(
        total_relationships=len(relationships),
        total_atomic_skills=len(taxonomy.atomic_skill_ids),
        issues=issues,
        prerequisite_dag_valid=not cycles,
        cycles_found=cycles,
        duplicate_edges=sorted(set(duplicate_edges)),
        invalid_references=sorted(invalid_references),
    )


def _unreachable_atomic_skills(
    relationships: Sequence[SkillRelationship],
    taxonomy: GrammarTaxonomy,
) -> list[str]:
    children: dict[str, set[str]] = defaultdict(set)
    for relationship in relationships:
        if relationship.relation_type == "parent_of":
            children[relationship.source_skill_id].add(relationship.target_skill_id)
    seen: set[str] = set()
    queue = deque([taxonomy.root_id])
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(children.get(node, set()))
    return [
        skill_id
        for skill_id in taxonomy.atomic_skill_ids
        if skill_id not in seen
    ]


def _relationship_context(relationship: SkillRelationship) -> dict[str, object]:
    return {
        "relationship_id": relationship.relationship_id,
        "source_skill_id": relationship.source_skill_id,
        "target_skill_id": relationship.target_skill_id,
        "relation_type": relationship.relation_type,
    }

