from __future__ import annotations

import queue
from datetime import datetime


LEVEL_EMOJI = {
    "INFO": "🟢",
    "WARN": "🟡",
    "WARNING": "🟡",
    "ERROR": "🔴",
    "DEBUG": "🔵",
}


class LogBus:
    """Small in-memory log queue.

    Runtime logs are intentionally not saved to files. The GUI drains this
    queue and keeps only a fixed number of lines in the text widget.
    """

    def __init__(self, echo: bool = False) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self.echo = echo

    def emit(self, message: str, level: str = "INFO") -> None:
        level = level.upper()
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = LEVEL_EMOJI.get(level, "⚪")
        line = f"{emoji} [{timestamp}] [{level}] {message}"
        self._queue.put(line)
        if self.echo:
            try:
                print(line, flush=True)
            except Exception:
                # PyInstaller --windowed apps have no console streams. Runtime
                # logs are still available in the GUI, so echo failures are safe
                # to ignore.
                pass

    def drain(self, limit: int = 200) -> list[str]:
        lines: list[str] = []
        for _ in range(limit):
            try:
                lines.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return lines
