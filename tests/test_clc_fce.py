from __future__ import annotations

import importlib.util
from pathlib import Path


_BASE = Path(__file__).parent / "knowledge_core" / "sources" / "clc_fce"

for _name in ("test_parser", "test_pipeline"):
    _path = _BASE / f"{_name}.py"
    _spec = importlib.util.spec_from_file_location(f"_clc_fce_{_name}", _path)
    _module = importlib.util.module_from_spec(_spec)
    assert _spec is not None
    assert _spec.loader is not None
    _spec.loader.exec_module(_module)
    globals().update(
        {
            key: value
            for key, value in vars(_module).items()
            if key.endswith("Tests")
        },
    )

