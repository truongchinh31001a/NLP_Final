from __future__ import annotations

import unittest
from datetime import datetime, timezone

from knowledge_core.mapping.egp.canonical import CANONICAL_GRAMMAR_V1_SKILLS
from knowledge_core.mapping.egp.mapper import create_mappings
from knowledge_core.sources.egp.models import RawEGPRecord


class EGPMappingRuleTests(unittest.TestCase):
    def test_present_simple_affirmative(self) -> None:
        mapping = self._map(
            self._record(
                category_id="present_simple",
                feature_type="FORM",
                feature_name="AFFIRMATIVE",
                can_do_statement="Can use the affirmative form.",
            ),
        )

        self.assertEqual(mapping.status, "exact")
        self.assertEqual(mapping.canonical_skill, "grammar.present_simple.affirmative")

    def test_present_simple_third_person_s(self) -> None:
        mapping = self._map(
            self._record(
                category_id="present_simple",
                can_do_statement="Can use the third person -s form.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.present_simple.third_person_s")

    def test_past_simple_irregular(self) -> None:
        mapping = self._map(
            self._record(
                category_id="past_simple",
                can_do_statement="Can use irregular verbs in the past simple.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.past_simple.irregular_verbs")

    def test_form_feature_in_unique_form_category_is_exact(self) -> None:
        mapping = self._map(
            self._record(
                category_id="present_continuous",
                feature_type="FORM",
                feature_name="QUESTIONS",
                can_do_statement="Can use wh- questions.",
            ),
        )

        self.assertEqual(mapping.status, "exact")
        self.assertEqual(mapping.canonical_skill, "grammar.present_continuous.form")

    def test_present_perfect_already(self) -> None:
        mapping = self._map(
            self._record(
                category_id="present_perfect_simple",
                feature_type="FORM/USE",
                feature_name="WITH 'ALREADY'",
                can_do_statement="Can use the present perfect with already.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.present_perfect.recent_result")

    def test_present_perfect_since_for(self) -> None:
        mapping = self._map(
            self._record(
                category_id="present_perfect_simple",
                feature_type="FORM/USE",
                feature_name="DURATION WITH 'SINCE'",
                can_do_statement="Can use since to talk about duration.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.present_perfect.since_for")

    def test_modal_can_ability(self) -> None:
        mapping = self._map(
            self._record(
                category_id="modality_can",
                feature_type="USE",
                feature_name="ABILITY",
                can_do_statement="Can use can to talk about ability.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.modality.can_ability")

    def test_modal_can_permission(self) -> None:
        mapping = self._map(
            self._record(
                category_id="modality_can",
                feature_type="USE",
                feature_name="PERMISSION",
                can_do_statement="Can use can to ask for permission.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.modality.can_permission")

    def test_articles(self) -> None:
        mapping = self._map(
            self._record(
                category_id="articles",
                feature_type="FORM",
                feature_name="'A' + ADJECTIVES",
                can_do_statement="Can use a and an before adjectives.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.articles.a_an")

    def test_conditional(self) -> None:
        mapping = self._map(
            self._record(
                category_id="conditional",
                feature_type="FORM/USE",
                feature_name="FIRST CONDITIONAL",
                can_do_statement="Can use if + present simple + will.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.conditionals.first")

    def test_passive(self) -> None:
        mapping = self._map(
            self._record(
                category_id="passives_form",
                feature_type="FORM/USE",
                feature_name="WITH 'BY' TO ADD INFORMATION",
                can_do_statement="Can use the passive with by to add information.",
            ),
        )

        self.assertEqual(mapping.canonical_skill, "grammar.passive.agent_by")

    def test_ambiguous_mapping(self) -> None:
        mapping = self._map(
            self._record(
                category_id="present_simple",
                feature_type="FORM/USE",
                feature_name="NEGATIVE QUESTIONS",
                can_do_statement="Can use present simple negative questions.",
            ),
        )

        self.assertEqual(mapping.status, "ambiguous")
        self.assertIsNone(mapping.canonical_skill)
        self.assertIn("grammar.present_simple.negative", mapping.secondary_candidates)

    def test_unmapped_advanced_feature(self) -> None:
        mapping = self._map(
            self._record(
                category_id="present_simple",
                feature_type="USE",
                feature_name="SPEECH ACT VERBS",
                can_do_statement="Can use speech act verbs in academic contexts.",
            ),
        )

        self.assertEqual(mapping.status, "unmapped")
        self.assertIsNone(mapping.canonical_skill)

    def test_every_source_record_receives_one_mapping(self) -> None:
        records = [
            self._record(source_record_id="egp_one"),
            self._record(source_record_id="egp_two"),
        ]

        mappings = create_mappings(records)

        self.assertEqual(len(mappings), 2)
        self.assertEqual(
            {mapping.source_record_id for mapping in mappings},
            {"egp_one", "egp_two"},
        )

    def test_taxonomy_constant_is_not_mutated(self) -> None:
        before = tuple(CANONICAL_GRAMMAR_V1_SKILLS)

        create_mappings([self._record()])

        self.assertEqual(tuple(CANONICAL_GRAMMAR_V1_SKILLS), before)

    def _map(self, record: RawEGPRecord):
        return create_mappings([record])[0]

    def _record(
        self,
        *,
        category_id: str = "present_simple",
        feature_type: str | None = "FORM",
        feature_name: str | None = "AFFIRMATIVE",
        can_do_statement: str = "Can use the affirmative form.",
        source_record_id: str = "egp_test_record",
    ) -> RawEGPRecord:
        return RawEGPRecord(
            source_record_id=source_record_id,
            category_id=category_id,
            super_category="PRESENT",
            sub_category=category_id.replace("_", " "),
            cefr_level="A1",
            feature_type=feature_type,
            feature_name=feature_name,
            can_do_statement=can_do_statement,
            example=None,
            details=None,
            source_row_number=2,
            source_file="fixture.xlsx",
            retrieved_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
            raw_payload={
                "Guideword": (
                    f"{feature_type}: {feature_name}"
                    if feature_type and feature_name
                    else None
                ),
            },
        )


if __name__ == "__main__":
    unittest.main()
