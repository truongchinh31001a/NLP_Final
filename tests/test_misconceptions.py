from __future__ import annotations

import importlib.util
from pathlib import Path


_TEST_PATH = (
    Path(__file__).parent
    / "knowledge_core"
    / "misconceptions"
    / "test_misconceptions.py"
)
_SPEC = importlib.util.spec_from_file_location("_misconceptions_test_impl", _TEST_PATH)
_MODULE = importlib.util.module_from_spec(_SPEC)
assert _SPEC is not None
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MODULE)

MisconceptionMiningTests = _MODULE.MisconceptionMiningTests
