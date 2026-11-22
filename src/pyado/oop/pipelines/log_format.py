"""Helpers that build Azure DevOps console log lines.

The pipeline log and the live feed render lines starting with ``##[...]``
markers specially.  The rules below were measured against the portal (130
line shapes sent through the log and the feed) and are why these helpers
exist instead of plain string formatting:

* ``##[section]``, ``##[command]`` and ``##[group]`` hide their marker and
  keep the rest of the line, but the viewer cuts about nine characters when
  anything precedes the marker, and cuts the text before a second marker of
  the same type on the same line.
* ``##[error]``, ``##[warning]``, ``##[debug]`` and ``##[info]`` are never cut.
* A carriage return splits a line and loses the text before it, and a null
  byte corrupts the line.
* Marker lines colour the text but never create build issues; only the
  ``issues`` field of a timeline record does.
"""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import re
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from enum import StrEnum

__all__ = [
    "Ansi",
    "LogLevel",
    "LogLines",
    "ansi",
    "command",
    "debug",
    "error",
    "format_line",
    "group",
    "info",
    "sanitize",
    "section",
    "warning",
]

_MARKER = re.compile(r"#\s?#\s?\[")
_HIDDEN_MARKERS = ("##[section]", "##[command]", "##[group]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1a\x1c-\x1f\x7f]")


class LogLevel(StrEnum):
    """Markers that colour a console line."""

    ERROR = "error"
    WARNING = "warning"
    DEBUG = "debug"
    INFO = "info"
    SECTION = "section"
    COMMAND = "command"


class Ansi(StrEnum):
    """ANSI colours that the portal renders (basic and bright, no 256-colour)."""

    RED = "31"
    GREEN = "32"
    YELLOW = "33"
    BLUE = "34"
    MAGENTA = "35"
    CYAN = "36"
    WHITE = "37"
    GREY = "90"
    BOLD = "1"


def sanitize(text: str) -> str:
    """Make *text* safe to send as exactly one log line.

    Carriage returns and newlines become spaces (a carriage return would split
    the displayed line and drop the text before it), control characters
    including NUL are removed, and a ``##[`` marker sequence inside the text
    becomes ``##[ `` (a space after the bracket), a shape the portal renders
    as plain text.  Variants such as ``## [`` and ``# #[`` would still count as
    markers, so they are rewritten the same way.

    Args:
        text: Arbitrary text that may contain line breaks or markers.

    Returns:
        A single-line string without control characters or active markers.
    """
    flat = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    flat = _CONTROL.sub("", flat)
    return _MARKER.sub("##[ ", flat)


def format_line(level: LogLevel | None, text: str) -> str:
    """Return one log line with an optional colour marker.

    ``section``, ``command`` and ``group`` markers are placed at the very start
    of the line; the text is sanitised so it cannot hold a second marker.

    Args:
        level: Marker to put in front of the text, or None for a plain line.
        text: The message; line breaks and markers inside are neutralised.

    Returns:
        The finished line without a trailing newline.
    """
    body = sanitize(text)
    if level is None:
        return body
    return f"##[{level.value}]{body}"


def error(text: str) -> str:
    """Return a red ``##[error]`` line (display only; creates no issue)."""
    return format_line(LogLevel.ERROR, text)


def warning(text: str) -> str:
    """Return an orange ``##[warning]`` line (display only; creates no issue)."""
    return format_line(LogLevel.WARNING, text)


def debug(text: str) -> str:
    """Return a purple ``##[debug]`` line."""
    return format_line(LogLevel.DEBUG, text)


def info(text: str) -> str:
    """Return a grey ``##[info]`` line."""
    return format_line(LogLevel.INFO, text)


def section(text: str) -> str:
    """Return a green ``##[section]`` line with the marker hidden by the viewer."""
    return format_line(LogLevel.SECTION, text)


def command(text: str) -> str:
    """Return a blue ``##[command]`` line with the marker hidden by the viewer."""
    return format_line(LogLevel.COMMAND, text)


def group(title: str, lines: Iterable[str]) -> list[str]:
    """Wrap *lines* in a foldable group.

    The group is collapsed in the log and expanded in the live feed.  The
    title is sanitised, and ``##[endgroup]`` is always the last line.

    Args:
        title: Group title shown on the fold header.
        lines: Lines inside the group, used as given.

    Returns:
        ``##[group]title``, the lines, then ``##[endgroup]``.
    """
    return [f"##[group]{sanitize(title)}", *lines, "##[endgroup]"]


def ansi(text: str, colour: Ansi, *, bold: bool = False) -> str:
    """Colour *text* with an ANSI escape sequence the portal renders.

    Args:
        text: The text to colour; sanitised first.
        colour: Colour from :class:`Ansi`.
        bold: Also set bold.

    Returns:
        The text wrapped in an SGR sequence and a reset.
    """
    codes = f"{Ansi.BOLD.value};{colour.value}" if bold else colour.value
    return f"\x1b[{codes}m{sanitize(text)}\x1b[0m"


class LogLines:
    r"""Collect log lines and render them for one append or one feed call.

    Example:
        >>> lines = LogLines()
        >>> lines.section("Deploy")
        >>> with lines.group("Details"):
        ...     lines.add("image: app:1.2")
        >>> lines.text()
        '##[section]Deploy\\n##[group]Details\\nimage: app:1.2\\n##[endgroup]\\n'
    """

    def __init__(self) -> None:
        """Create an empty collection."""
        self._lines: list[str] = []

    def add(self, text: str) -> None:
        """Add a plain line."""
        self._lines.append(format_line(None, text))

    def error(self, text: str) -> None:
        """Add a red ``##[error]`` line."""
        self._lines.append(error(text))

    def warning(self, text: str) -> None:
        """Add an orange ``##[warning]`` line."""
        self._lines.append(warning(text))

    def section(self, text: str) -> None:
        """Add a green ``##[section]`` line."""
        self._lines.append(section(text))

    def command(self, text: str) -> None:
        """Add a blue ``##[command]`` line."""
        self._lines.append(command(text))

    @contextmanager
    def group(self, title: str) -> Iterator[None]:
        """Open a group and always close it, even if the body raises.

        Args:
            title: Group title shown on the fold header.

        Yields:
            Nothing; lines added inside the block belong to the group.
        """
        self._lines.append(f"##[group]{sanitize(title)}")
        try:
            yield
        finally:
            self._lines.append("##[endgroup]")

    def lines(self) -> list[str]:
        """Return a copy of the collected lines."""
        return list(self._lines)

    def text(self) -> str:
        """Return the lines joined for one log append, ending in a newline."""
        return "".join(f"{line}\n" for line in self._lines)
