from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_core.sources.cefr.config import CEFRConfigError, load_cefr_config


class CEFRConfigTests(unittest.TestCase):
    def test_default_config_loads_v1_scales(self) -> None:
        config = load_cefr_config()

        scales = config.select_scales()
        self.assertEqual(config.source.name, "cefr_companion_volume")
        self.assertEqual(config.source.year, 2020)
        self.assertEqual(len(scales), 19)
        self.assertEqual(scales[0].id, "overall_oral_comprehension")
        self.assertEqual(scales[0].domain, "reception")
        self.assertEqual(
            config.scale_by_id()["grammatical_accuracy"].subdomain,
            "grammar",
        )

    def test_config_selection_filters_domain_and_section(self) -> None:
        config = load_cefr_config()

        production = config.select_scales(domain="production")
        chapter5 = config.select_scales(section="chapter5")

        self.assertEqual(len(production), 6)
        self.assertTrue(all(scale.domain == "production" for scale in production))
        self.assertEqual(len(chapter5), 5)
        self.assertTrue(
            all(scale.domain == "linguistic_competence" for scale in chapter5),
        )

    def test_config_rejects_duplicate_scale_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "cefr_sections.yaml"
            path.write_text(
                """
chapter2:
  section: "2.6 CEFR Common Reference Levels"
  page_start: 1
  page_end: 2
source:
  source_file: "data/external/cefr/CEFR Companion Volume_eng.pdf"
sections:
  reception:
    chapter: "3"
    section: "Reception"
    descriptor_type: communicative_activity
    page_start: 1
    page_end: 2
    scales:
      - id: repeated
        name: "Overall oral comprehension"
  production:
    chapter: "3"
    section: "Production"
    descriptor_type: communicative_activity
    page_start: 3
    page_end: 4
    scales:
      - id: repeated
        name: "Overall oral production"
""",
                encoding="utf-8",
            )

            with self.assertRaises(CEFRConfigError):
                load_cefr_config(path)


if __name__ == "__main__":
    unittest.main()

