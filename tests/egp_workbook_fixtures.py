from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Sequence

from openpyxl import Workbook


def write_xlsx(path: Path, rows: Sequence[Sequence[object]]) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(list(row))
    workbook.save(path)
    workbook.close()
    return path


def xlsx_bytes(rows: Sequence[Sequence[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(list(row))
    handle = BytesIO()
    workbook.save(handle)
    workbook.close()
    return handle.getvalue()
