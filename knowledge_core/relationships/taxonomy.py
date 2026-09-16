from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence


TAXONOMY_ROOT = "grammar"


@dataclass(slots=True, frozen=True)
class GrammarTaxonomy:
    root_id: str
    atomic_skill_ids: tuple[str, ...]
    group_node_ids: tuple[str, ...]
    all_node_ids: frozenset[str]
    parent_by_node: dict[str, str]
    children_by_parent: dict[str, tuple[str, ...]]

    @property
    def taxonomy_hash(self) -> str:
        raw = "\n".join(self.atomic_skill_ids)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_grammar_taxonomy(canonical_skills: Sequence[str]) -> GrammarTaxonomy:
    atomic_skill_ids = tuple(canonical_skills)
    parent_by_node: dict[str, str] = {}
    all_nodes = {TAXONOMY_ROOT, *atomic_skill_ids}

    for skill_id in atomic_skill_ids:
        parent = immediate_parent(skill_id)
        parent_by_node[skill_id] = parent
        parts = skill_id.split(".")
        for index in range(1, len(parts)):
            all_nodes.add(".".join(parts[:index]))
        all_nodes.add(parent)

    group_nodes = sorted(all_nodes - set(atomic_skill_ids) - {TAXONOMY_ROOT})
    for group_node in group_nodes:
        if group_node == TAXONOMY_ROOT:
            continue
        parent_by_node[group_node] = immediate_parent(group_node)

    children_by_parent: dict[str, list[str]] = defaultdict(list)
    for node, parent in parent_by_node.items():
        children_by_parent[parent].append(node)

    return GrammarTaxonomy(
        root_id=TAXONOMY_ROOT,
        atomic_skill_ids=atomic_skill_ids,
        group_node_ids=tuple(group_nodes),
        all_node_ids=frozenset(all_nodes),
        parent_by_node=parent_by_node,
        children_by_parent={
            parent: tuple(sorted(children))
            for parent, children in children_by_parent.items()
        },
    )


def immediate_parent(node_id: str) -> str:
    parts = node_id.split(".")
    if len(parts) <= 1:
        return TAXONOMY_ROOT
    return ".".join(parts[:-1])


def is_immediate_parent(parent_id: str, child_id: str) -> bool:
    return immediate_parent(child_id) == parent_id

