from __future__ import annotations

from datetime import datetime, timezone
import unittest

from knowledge_core.alignment.egp_evidence import collect_egp_evidence
from knowledge_core.mapping.egp.models import EGPCanonicalMapping
from knowledge_core.sources.egp.models import RawEGPRecord


class EGPEvidenceTests(unittest.TestCase):
    def test_exact_and_candidate_mappings_become_direct_evidence(self) -> None:
        records = [
            egp_record("egp_1", "B1"),
            egp_record("egp_2", "B2"),
        ]
        mappings = [
            egp_mapping("egp_1", "grammar.present_perfect.experience", "exact", 1.0),
            egp_mapping("egp_2", "grammar.present_perfect.experience", "candidate", 0.8),
        ]

        bundle = collect_egp_evidence(
            records,
            mappings,
            establishing_statuses={"exact", "candidate"},
            ambiguous_statuses={"ambiguous"},
            status_weights={"exact": 1.0, "candidate": 0.65},
        )

        evidence = bundle.direct_by_skill["grammar.present_perfect.experience"]
        self.assertEqual(len(evidence), 2)
        self.assertEqual([item.source_cefr_level for item in evidence], ["B1", "B2"])
        self.assertEqual(evidence[1].confidence, 0.52)

    def test_ambiguous_mappings_are_kept_for_review_not_direct_evidence(self) -> None:
        records = [egp_record("egp_ambiguous", "A2")]
        mappings = [
            EGPCanonicalMapping(
                mapping_id="map_ambiguous",
                source_record_id="egp_ambiguous",
                canonical_skill=None,
                secondary_candidates=[
                    "grammar.past_simple.regular_verbs",
                    "grammar.past_simple.irregular_verbs",
                ],
                status="ambiguous",
                confidence=0.55,
                reason="Form mentions regular and irregular verbs.",
                matched_terms=["regular and irregular"],
                review_status="needs_review",
            ),
        ]

        bundle = collect_egp_evidence(
            records,
            mappings,
            establishing_statuses={"exact", "candidate"},
            ambiguous_statuses={"ambiguous"},
            status_weights={"exact": 1.0, "candidate": 0.65},
        )

        self.assertEqual(bundle.direct_evidence, [])
        self.assertIn("grammar.past_simple.regular_verbs", bundle.ambiguous_by_skill)

    def test_non_ambiguous_secondary_candidates_are_preserved_as_candidate_evidence(
        self,
    ) -> None:
        records = [egp_record("egp_secondary", "B1")]
        mappings = [
            EGPCanonicalMapping(
                mapping_id="map_secondary",
                source_record_id="egp_secondary",
                canonical_skill="grammar.articles.zero_article",
                secondary_candidates=["grammar.articles.generic_reference"],
                status="candidate",
                confidence=0.86,
                reason="No-article feature with generic reference.",
                matched_terms=["no article"],
                review_status="pending",
            ),
        ]

        bundle = collect_egp_evidence(
            records,
            mappings,
            establishing_statuses={"exact", "candidate"},
            ambiguous_statuses={"ambiguous"},
            status_weights={"exact": 1.0, "candidate": 0.65},
        )

        self.assertEqual(len(bundle.direct_by_skill["grammar.articles.zero_article"]), 1)
        secondary = bundle.direct_by_skill["grammar.articles.generic_reference"][0]
        self.assertEqual(secondary.source_cefr_level, "B1")
        self.assertEqual(secondary.provenance["relationship"], "secondary_candidate")


def egp_record(source_record_id: str, cefr_level: str) -> RawEGPRecord:
    return RawEGPRecord(
        source_record_id=source_record_id,
        category_id="present_perfect_simple",
        cefr_level=cefr_level,
        can_do_statement="Can use the present perfect to describe experience.",
        source_row_number=2,
        source_file="source.xlsx",
        retrieved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def egp_mapping(
    source_record_id: str,
    canonical_skill: str,
    status: str,
    confidence: float,
) -> EGPCanonicalMapping:
    return EGPCanonicalMapping(
        mapping_id=f"map_{source_record_id}",
        source_record_id=source_record_id,
        canonical_skill=canonical_skill,
        status=status,
        confidence=confidence,
        reason="Matched fixture.",
        matched_terms=["fixture"],
        review_status="approved" if status == "exact" else "pending",
    )


if __name__ == "__main__":
    unittest.main()

