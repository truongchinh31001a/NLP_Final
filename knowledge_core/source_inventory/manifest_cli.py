from __future__ import annotations

import logging

from knowledge_core.source_inventory.manifest import build_source_manifest


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    manifest = build_source_manifest()
    logger.info("Sources: %s", manifest["source_count"])
    logger.info("Manifest files: %s", manifest["file_count"])
    logger.info("Validation passed: %s", manifest["validation"]["passed"])
    logger.info("Warnings: %s", manifest["validation"]["warning_count"])
    return 0 if manifest["validation"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
