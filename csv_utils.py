from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, TextIO


CSV_ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "utf-16",
    "utf-16le",
    "utf-16be",
    "gb18030",
    "gbk",
    "cp936",
)


def open_text_csv(path: str | Path, encodings: Iterable[str] = CSV_ENCODINGS) -> TextIO:
    """Open a CSV text file with common UTF-8 and Chinese Windows encodings."""

    file_path = Path(path)
    data = file_path.read_bytes()
    last_error: UnicodeDecodeError | None = None

    for encoding in encodings:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        if not looks_like_csv_text(text):
            continue

        return io.StringIO(text, newline="")

    if last_error:
        raise UnicodeDecodeError(
            last_error.encoding,
            last_error.object,
            last_error.start,
            last_error.end,
            f"Unable to detect CSV encoding. Tried: {', '.join(encodings)}",
        )

    raise ValueError(f"Unable to read CSV file: {file_path}")


def looks_like_csv_text(text: str) -> bool:
    sample = text[:500]
    if "\x00" in sample:
        return False
    first_line = text.splitlines()[0] if text.splitlines() else ""
    return "," in first_line
