"""Startup banner for Firmngin device clients."""

from __future__ import annotations

_BANNER_LINES = (
    "",
    r"   __ _                            _            _            ",
    r"  / _(_)                          (_)          | |           ",
    r" | |_ _ _ __ _ __ ___  _ __   __ _ _ _ __    __| | _____   __",
    r" |  _| | '__| '_ ` _ \| '_ \ / _` | | '_ \  / _` |/ _ \ \ / /",
    r" | | | | |  | | | | | | | | | (_| | | | | || (_| |  __/\ V / ",
    r" |_| |_|_|  |_| |_| |_|_| |_|\__, |_|_| |_(_)__,_|\___| \_/  ",
    r"                              __/ |                          ",
    r" The AIoT Platform           |___/                           ",
)


def print_startup_banner(version: str) -> None:
    for line in _BANNER_LINES:
        print(line)
    print(f" Version: {version}")
    print()


__all__ = ["print_startup_banner"]
