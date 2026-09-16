from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable, Sequence

from knowledge_core.relationships.models import (
    RelationshipGraphAnalysis,
    SkillGraphNodeSummary,
    SkillRelationship,
)
from knowledge_core.relationships.taxonomy import GrammarTaxonomy


@dataclass(slots=True)
class SkillRelationshipGraph:
    relationships: list[SkillRelationship]
    taxonomy: GrammarTaxonomy

    def get_prerequisites(self, skill_id: str) -> list[str]:
        return sorted(self._hard_prerequisites_by_target().get(skill_id, set()))

    def get_transitive_prerequisites(self, skill_id: str) -> list[str]:
        seen: set[str] = set()
        stack = list(self.get_prerequisites(skill_id))
        while stack:
            prerequisite = stack.pop()
            if prerequisite in seen:
                continue
            seen.add(prerequisite)
            stack.extend(self.get_prerequisites(prerequisite))
        return sorted(seen, key=self._taxonomy_order)

    def get_unlocked_skills(self, mastered_skill_ids: Iterable[str]) -> list[str]:
        mastered = set(mastered_skill_ids)
        unlocked = []
        for skill_id in self.taxonomy.atomic_skill_ids:
            if skill_id in mastered:
                continue
            if self.is_unlocked(skill_id, mastered):
                unlocked.append(skill_id)
        return unlocked

    def is_unlocked(self, skill_id: str, mastered_skill_ids: Iterable[str]) -> bool:
        mastered = set(mastered_skill_ids)
        return set(self.get_prerequisites(skill_id)).issubset(mastered)

    def get_learning_path(self, target_skill_id: str) -> list[str]:
        needed = set(self.get_transitive_prerequisites(target_skill_id)) | {
            target_skill_id,
        }
        incoming = {skill_id: 0 for skill_id in needed}
        outgoing: dict[str, set[str]] = {skill_id: set() for skill_id in needed}
        for source, targets in self._hard_unlocks_by_source().items():
            if source not in needed:
                continue
            for target in targets:
                if target in needed:
                    outgoing[source].add(target)
                    incoming[target] += 1
        ready = deque(sorted(
            [skill_id for skill_id, count in incoming.items() if count == 0],
            key=self._taxonomy_order,
        ))
        path: list[str] = []
        while ready:
            skill_id = ready.popleft()
            path.append(skill_id)
            for unlocked in sorted(outgoing[skill_id], key=self._taxonomy_order):
                incoming[unlocked] -= 1
                if incoming[unlocked] == 0:
                    ready.append(unlocked)
        if target_skill_id in path:
            target_index = path.index(target_skill_id)
            return path[: target_index + 1]
        return path

    def analyze(self) -> RelationshipGraphAnalysis:
        hard_prereq = self._hard_prerequisites_by_target()
        hard_unlocks = self._hard_unlocks_by_source()
        non_structural_neighbors = self._non_structural_neighbors()
        in_degree, out_degree = self._degrees()
        node_summaries: dict[str, SkillGraphNodeSummary] = {}
        depths = {
            skill_id: len(self.get_transitive_prerequisites(skill_id))
            for skill_id in self.taxonomy.atomic_skill_ids
        }
        for skill_id in self.taxonomy.atomic_skill_ids:
            node_summaries[skill_id] = SkillGraphNodeSummary(
                skill_id=skill_id,
                in_degree=in_degree.get(skill_id, 0),
                out_degree=out_degree.get(skill_id, 0),
                prerequisite_depth=depths[skill_id],
                direct_prerequisites=sorted(
                    hard_prereq.get(skill_id, set()),
                    key=self._taxonomy_order,
                ),
                transitive_prerequisites=self.get_transitive_prerequisites(skill_id),
                direct_unlocks=sorted(
                    hard_unlocks.get(skill_id, set()),
                    key=self._taxonomy_order,
                ),
                related_skills=self._semantic_neighbors(skill_id, "related_to"),
                contrast_skills=self._semantic_neighbors(skill_id, "contrast_with"),
            )
        root_prerequisite_skills = [
            skill_id
            for skill_id in self.taxonomy.atomic_skill_ids
            if not hard_prereq.get(skill_id) and hard_unlocks.get(skill_id)
        ]
        terminal_skills = [
            skill_id
            for skill_id in self.taxonomy.atomic_skill_ids
            if hard_prereq.get(skill_id) and not hard_unlocks.get(skill_id)
        ]
        isolated_skills = [
            skill_id
            for skill_id in self.taxonomy.atomic_skill_ids
            if not non_structural_neighbors.get(skill_id)
        ]
        longest_path = self._longest_prerequisite_path()
        return RelationshipGraphAnalysis(
            total_nodes=len(self.taxonomy.all_node_ids),
            total_atomic_skills=len(self.taxonomy.atomic_skill_ids),
            root_prerequisite_skills=root_prerequisite_skills,
            terminal_skills=terminal_skills,
            isolated_skills=isolated_skills,
            connected_components=self._connected_components(non_structural_neighbors),
            max_prerequisite_depth=max(depths.values(), default=0),
            longest_prerequisite_path=longest_path,
            node_summaries=node_summaries,
        )

    def find_prerequisite_cycles(self) -> list[list[str]]:
        adjacency = self._hard_unlocks_by_source()
        visiting: set[str] = set()
        visited: set[str] = set()
        stack: list[str] = []
        cycles: list[list[str]] = []

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                if node in stack:
                    start = stack.index(node)
                    cycles.append(stack[start:] + [node])
                return
            visiting.add(node)
            stack.append(node)
            for neighbor in adjacency.get(node, set()):
                visit(neighbor)
            stack.pop()
            visiting.remove(node)
            visited.add(node)

        for skill_id in self.taxonomy.atomic_skill_ids:
            visit(skill_id)
        return _deduplicate_cycles(cycles)

    def _hard_prerequisites_by_target(self) -> dict[str, set[str]]:
        prerequisites: dict[str, set[str]] = defaultdict(set)
        for relationship in self.relationships:
            if relationship.relation_type == "prerequisite_of":
                prerequisites[relationship.target_skill_id].add(
                    relationship.source_skill_id,
                )
        return prerequisites

    def _hard_unlocks_by_source(self) -> dict[str, set[str]]:
        unlocks: dict[str, set[str]] = defaultdict(set)
        for relationship in self.relationships:
            if relationship.relation_type == "prerequisite_of":
                unlocks[relationship.source_skill_id].add(
                    relationship.target_skill_id,
                )
        return unlocks

    def _non_structural_neighbors(self) -> dict[str, set[str]]:
        neighbors: dict[str, set[str]] = defaultdict(set)
        for relationship in self.relationships:
            if relationship.relation_type == "parent_of":
                continue
            source = relationship.source_skill_id
            target = relationship.target_skill_id
            neighbors[source].add(target)
            neighbors[target].add(source)
        return neighbors

    def _degrees(self) -> tuple[dict[str, int], dict[str, int]]:
        in_degree: dict[str, int] = defaultdict(int)
        out_degree: dict[str, int] = defaultdict(int)
        for relationship in self.relationships:
            out_degree[relationship.source_skill_id] += 1
            in_degree[relationship.target_skill_id] += 1
            if relationship.bidirectional:
                out_degree[relationship.target_skill_id] += 1
                in_degree[relationship.source_skill_id] += 1
        return in_degree, out_degree

    def _semantic_neighbors(self, skill_id: str, relation_type: str) -> list[str]:
        neighbors: set[str] = set()
        for relationship in self.relationships:
            if relationship.relation_type != relation_type:
                continue
            if relationship.source_skill_id == skill_id:
                neighbors.add(relationship.target_skill_id)
            if relationship.bidirectional and relationship.target_skill_id == skill_id:
                neighbors.add(relationship.source_skill_id)
        return sorted(neighbors, key=self._taxonomy_order)

    def _connected_components(
        self,
        neighbors: dict[str, set[str]],
    ) -> list[list[str]]:
        remaining = set(self.taxonomy.atomic_skill_ids)
        components: list[list[str]] = []
        while remaining:
            start = min(remaining, key=self._taxonomy_order)
            stack = [start]
            component: set[str] = set()
            while stack:
                node = stack.pop()
                if node in component:
                    continue
                component.add(node)
                stack.extend(neighbors.get(node, set()) - component)
            remaining -= component
            components.append(sorted(component, key=self._taxonomy_order))
        return components

    def _longest_prerequisite_path(self) -> list[str]:
        adjacency = self._hard_unlocks_by_source()
        memo: dict[str, list[str]] = {}

        def longest_from(node: str) -> list[str]:
            if node in memo:
                return memo[node]
            best = [node]
            for neighbor in sorted(adjacency.get(node, set()), key=self._taxonomy_order):
                candidate = [node] + longest_from(neighbor)
                if len(candidate) > len(best):
                    best = candidate
            memo[node] = best
            return best

        best_path: list[str] = []
        for skill_id in self.taxonomy.atomic_skill_ids:
            candidate = longest_from(skill_id)
            if len(candidate) > len(best_path):
                best_path = candidate
        return best_path

    def _taxonomy_order(self, skill_id: str) -> int:
        try:
            return list(self.taxonomy.atomic_skill_ids).index(skill_id)
        except ValueError:
            return 10_000


def _deduplicate_cycles(cycles: Sequence[Sequence[str]]) -> list[list[str]]:
    seen: set[tuple[str, ...]] = set()
    deduplicated: list[list[str]] = []
    for cycle in cycles:
        if not cycle:
            continue
        body = list(cycle[:-1] if cycle[0] == cycle[-1] else cycle)
        rotations = [
            tuple(body[index:] + body[:index])
            for index in range(len(body))
        ]
        key = min(rotations)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(body + [body[0]])
    return deduplicated

