"""Shared PEM material helpers for TLS clients."""

from __future__ import annotations

import contextlib
import tempfile
from pathlib import Path


class TempPemFiles:
    """Write in-memory PEM strings to temp files for libraries that need paths."""

    __slots__ = ("_files",)

    def __init__(self) -> None:
        self._files: list[Path] = []

    def write(self, content: str | None) -> str | None:
        if content is None:
            return None
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as file:
            file.write(content)
            file.flush()
            path = Path(file.name)
        self._files.append(path)
        return str(path)

    def cleanup(self) -> None:
        for path in self._files:
            with contextlib.suppress(FileNotFoundError):
                path.unlink()
        self._files.clear()


__all__ = ["TempPemFiles"]
