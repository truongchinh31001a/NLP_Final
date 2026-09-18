from __future__ import annotations

import unittest

from knowledge_core.error_mapping.adjudication import classify_agreement_edit


class CLCAGVAdjudicationTests(unittest.TestCase):
    def test_approves_clear_third_person_s_pair(self) -> None:
        decision, _ = classify_agreement_edit("work", "works", set())
        self.assertEqual(decision, "APPROVE")

    def test_approves_ud_irregular_pair(self) -> None:
        decision, _ = classify_agreement_edit("have", "has", {("has", "have")})
        self.assertEqual(decision, "APPROVE")

    def test_rejects_be_agreement(self) -> None:
        decision, _ = classify_agreement_edit("are", "is", set())
        self.assertEqual(decision, "REJECT")

    def test_retains_ambiguous_edit_for_review(self) -> None:
        decision, _ = classify_agreement_edit("go", "went", set())
        self.assertEqual(decision, "NEEDS_REVIEW")

    def test_handles_multi_token_single_morphology_change(self) -> None:
        decision, _ = classify_agreement_edit("often work", "often works", set())
        self.assertEqual(decision, "APPROVE")


if __name__ == "__main__":
    unittest.main()
