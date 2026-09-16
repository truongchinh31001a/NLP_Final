from __future__ import annotations

import unittest
import importlib.util
from pathlib import Path


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    root = Path(__file__).parent
    suite = unittest.TestSuite()
    for test_dir in [
        root / "knowledge_core" / "sources" / "egp",
        root / "knowledge_core" / "mapping" / "egp",
        root / "knowledge_core" / "sources" / "cefr",
        root / "knowledge_core" / "alignment",
        root / "knowledge_core" / "relationships",
        root / "knowledge_core" / "assessment",
        root / "knowledge_core" / "storage",
        root / "knowledge_core" / "repository",
    ]:
        for path in sorted(test_dir.glob(pattern or "test*.py")):
            module = _load_module(path)
            suite.addTests(loader.loadTestsFromModule(module))
    return suite


def _load_module(path: Path):
    module_name = "egp_nested_tests_" + "_".join(path.with_suffix("").parts[-5:])
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load test module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
