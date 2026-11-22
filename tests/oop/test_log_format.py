"""Tests for pyado.oop.pipelines.log_format."""
# Copyright (c) 2023, Fred Stober
# SPDX-License-Identifier: MIT

import re
from collections.abc import Callable

import pytest

from pyado.oop import LogLines
from pyado.oop.pipelines import log_format
from pyado.oop.pipelines.log_format import Ansi, LogLevel


class TestSanitize:
    """Making arbitrary text safe for one log line."""

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("plain", "plain"),
            ("a\nb", "a b"),
            ("a\r\nb", "a b"),
            ("a\rb", "a b"),
            ("nul\x00byte", "nulbyte"),
            ("bell\x07char", "bellchar"),
            ("keep\ttab", "keep\ttab"),
            ("##[error]x", "##[ error]x"),
            ("## [error]x", "##[ error]x"),
            ("# #[section]x", "##[ section]x"),
            ("a ##[section] b ##[section] c", "a ##[ section] b ##[ section] c"),
        ],
    )
    def test_sanitize(self, text: str, expected: str) -> None:
        assert log_format.sanitize(text) == expected

    def test_sanitised_text_cannot_carry_a_marker(self) -> None:
        cleaned = log_format.sanitize("##[group]##[endgroup]##[error]")
        assert not re.search(r"##\[(?! )", cleaned)

    def test_the_escape_character_is_kept_for_ansi_colours(self) -> None:
        assert log_format.sanitize("\x1b[31mred\x1b[0m") == "\x1b[31mred\x1b[0m"


class TestLines:
    """Lines with a colour marker."""

    @pytest.mark.parametrize(
        ("helper", "marker"),
        [
            (log_format.error, "error"),
            (log_format.warning, "warning"),
            (log_format.debug, "debug"),
            (log_format.info, "info"),
            (log_format.section, "section"),
            (log_format.command, "command"),
        ],
    )
    def test_marker_is_at_the_line_start(
        self, helper: Callable[[str], str], marker: str
    ) -> None:
        assert helper("hello") == f"##[{marker}]hello"

    def test_text_cannot_add_a_second_marker(self) -> None:
        assert log_format.section("a ##[section] b") == "##[section]a ##[ section] b"

    def test_plain_line_has_no_marker(self) -> None:
        assert log_format.format_line(None, "x\ny") == "x y"

    def test_format_line_with_level(self) -> None:
        assert log_format.format_line(LogLevel.ERROR, "x") == "##[error]x"

    def test_group_wraps_the_lines(self) -> None:
        assert log_format.group("T", ["a", "b"]) == [
            "##[group]T",
            "a",
            "b",
            "##[endgroup]",
        ]

    def test_group_title_is_sanitised(self) -> None:
        assert log_format.group("##[group]x", [])[0] == "##[group]##[ group]x"


class TestAnsi:
    """ANSI colouring."""

    def test_colour_and_reset(self) -> None:
        assert log_format.ansi("hi", Ansi.RED) == "\x1b[31mhi\x1b[0m"

    def test_bold_colour(self) -> None:
        assert log_format.ansi("hi", Ansi.GREEN, bold=True) == "\x1b[1;32mhi\x1b[0m"

    def test_text_is_sanitised(self) -> None:
        assert log_format.ansi("a\nb", Ansi.BLUE) == "\x1b[34ma b\x1b[0m"


class TestLogLines:
    """Collecting lines for one append."""

    def test_collects_every_kind(self) -> None:
        lines = LogLines()
        lines.section("S")
        lines.command("C")
        lines.add("plain")
        lines.error("E")
        lines.warning("W")
        assert lines.lines() == [
            "##[section]S",
            "##[command]C",
            "plain",
            "##[error]E",
            "##[warning]W",
        ]

    def test_text_ends_every_line_with_a_newline(self) -> None:
        lines = LogLines()
        lines.add("a")
        lines.add("b")
        assert lines.text() == "a\nb\n"

    def test_group_context_closes_the_group(self) -> None:
        lines = LogLines()
        with lines.group("G"):
            lines.add("inside")
        assert lines.lines() == ["##[group]G", "inside", "##[endgroup]"]

    def test_group_is_closed_when_the_body_raises(self) -> None:
        lines = LogLines()
        with pytest.raises(RuntimeError), lines.group("G"):
            raise RuntimeError
        assert lines.lines()[-1] == "##[endgroup]"

    def test_lines_returns_a_copy(self) -> None:
        lines = LogLines()
        lines.add("a")
        lines.lines().append("b")
        assert lines.lines() == ["a"]
