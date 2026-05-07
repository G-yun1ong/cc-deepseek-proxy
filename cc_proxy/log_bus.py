from __future__ import annotations

import queue
import sys
from datetime import datetime
from typing import TextIO


LEVEL_EMOJI = {
    "INFO": "🟢",
    "WARN": "🟡",
    "WARNING": "🟡",
    "ERROR": "🔴",
    "DEBUG": "🔵",
}


def _configure_stream(stream: TextIO | None) -> None:
    if stream is None:
        return
    reconfigure = getattr(stream, "reconfigure", None)
    if not callable(reconfigure):
        return
    try:
        reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass


def configure_stdio_for_unicode() -> None:
    """Prefer UTF-8 text streams so console logs can include Chinese and emoji."""
    _configure_stream(sys.stdout)
    _configure_stream(sys.stderr)


def write_console_line(line: str, stream: TextIO | None = None) -> None:
    """Write one Unicode log line without letting console encoding crash the app."""
    stream = stream or sys.stdout
    text = line + "\n"
    try:
        stream.write(text)
        stream.flush()
        return
    except UnicodeEncodeError:
        buffer = getattr(stream, "buffer", None)
        if buffer is not None:
            try:
                buffer.write(text.encode("utf-8", errors="backslashreplace"))
                buffer.flush()
                return
            except Exception:
                pass
    except Exception:
        return

    try:
        encoding = stream.encoding or "utf-8"
        safe_text = text.encode(encoding, errors="backslashreplace").decode(encoding, errors="replace")
        stream.write(safe_text)
        stream.flush()
    except Exception:
        pass


class LogBus:
    """Small in-memory log queue.

    Runtime logs are intentionally not saved to files. The GUI drains this
    queue and keeps only a fixed number of lines in the text widget.
    """

    def __init__(self, echo: bool = False) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self.echo = echo
        if echo:
            configure_stdio_for_unicode()

    def emit(self, message: str, level: str = "INFO") -> None:
        level = level.upper()
        timestamp = datetime.now().strftime("%H:%M:%S")
        emoji = LEVEL_EMOJI.get(level, "⚪")
        line = f"{emoji} [{timestamp}] [{level}] {message}"
        self._queue.put(line)
        if self.echo:
            # PyInstaller --windowed apps may not have console streams. Runtime
            # logs are still available in the GUI, so output failures are safe.
            write_console_line(line)

    def drain(self, limit: int = 200) -> list[str]:
        lines: list[str] = []
        for _ in range(limit):
            try:
                lines.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return lines
