"""Unit tests for startup banner output."""

from __future__ import annotations

from firmngin._banner import print_startup_banner


def test_print_startup_banner_includes_brand_and_version(capsys) -> None:
    print_startup_banner("0.1.0")

    output = capsys.readouterr().out

    assert "|___/" in output
    assert "Version: 0.1.0" in output
    assert "The AIoT Platform" in output

