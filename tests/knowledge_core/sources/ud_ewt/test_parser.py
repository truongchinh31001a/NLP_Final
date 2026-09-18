from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.sources.ud_ewt import features
from knowledge_core.sources.ud_ewt.parser import parse_conllu_file, parse_deps, parse_feature_map

from tests.knowledge_core.sources.ud_ewt.fixtures import SAMPLE_CONLLU


class UDEWTParserTests(unittest.TestCase):
    def test_parse_feature_map_splits_values(self) -> None:
        self.assertEqual(
            parse_feature_map("Number=Sing|Person=3|Tense=Pres"),
            {"Number": ["Sing"], "Person": ["3"], "Tense": ["Pres"]},
        )
        self.assertEqual(parse_feature_map("_"), {})

    def test_parse_enhanced_dependencies(self) -> None:
        self.assertEqual(
            parse_deps("0:root|4:nsubj:pass"),
            [{"head": "0", "relation": "root"}, {"head": "4", "relation": "nsubj:pass"}],
        )

    def test_parse_sentence_comments_tokens_multiword_and_empty_nodes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.conllu"
            path.write_text(SAMPLE_CONLLU, encoding="utf-8")

            sentences = list(parse_conllu_file(path, split="dev"))

        self.assertEqual(len(sentences), 3)
        first = sentences[0]
        self.assertEqual(first.sentence_id, "s1")
        self.assertEqual(first.text, "They've been seen by John.")
        self.assertEqual(first.newdoc_id, "doc1")
        self.assertTrue(first.tokens[0].is_multiword)
        self.assertEqual(first.tokens[1].feats["Person"], ["3"])
        self.assertEqual(first.tokens[1].deps[0]["relation"], "nsubj:pass")

        second = sentences[1]
        empty = [token for token in second.tokens if token.is_empty_node]
        self.assertEqual(len(empty), 1)
        self.assertEqual(empty[0].token_id, "2.1")
        self.assertEqual(empty[0].deps[0]["relation"], "advmod")

    def test_structural_helper_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.conllu"
            path.write_text(SAMPLE_CONLLU, encoding="utf-8")
            sentences = list(parse_conllu_file(path, split="dev"))

        self.assertTrue(features.has_present_perfect_structure(sentences[0]))
        self.assertTrue(features.has_passive_structure(sentences[0]))
        self.assertTrue(features.has_agent_by_structure(sentences[0]))
        self.assertTrue(features.has_article_noun_structure(sentences[2], article="the"))
        self.assertTrue(features.has_modal_auxiliary(sentences[2], "can"))


if __name__ == "__main__":
    unittest.main()

