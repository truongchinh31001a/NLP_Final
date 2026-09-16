from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from knowledge_core.source_inventory.inventory import inspect_sources


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m knowledge_core.source_inventory.cli",
        description="Inspect Knowledge Core V1 source inventory without ingesting raw data.",
    )
    parser.add_argument(
        "--workspace",
        default=".",
        help="Repository root; defaults to the current working directory.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/reports/source_inventory",
        help="Directory for generated inventory reports.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run source discovery, inspection, and reporting.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        result = inspect_sources(Path(args.workspace), Path(args.output_dir))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["validation"]["passed"] else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
