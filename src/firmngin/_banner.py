"""Startup banner for Firmngin device clients."""

from __future__ import annotations

_BANNER_LINES = (
    "",
    "███████╗██╗██████╗ ███╗   ███╗███╗   ██╗ ██████╗ ██╗███╗   ██╗",
    "██╔════╝██║██╔══██╗████╗ ████║████╗  ██║██╔════╝ ██║████╗  ██║",
    "█████╗  ██║██████╔╝██╔████╔██║██╔██╗ ██║██║  ███╗██║██╔██╗ ██║",
    "██╔══╝  ██║██╔══██╗██║╚██╔╝██║██║╚██╗██║██║   ██║██║██║╚██╗██║",
    "██║     ██║██║  ██║██║ ╚═╝ ██║██║ ╚████║╚██████╔╝██║██║ ╚████║",
    "╚═╝     ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝",
)


def print_startup_banner(version: str) -> None:
    for line in _BANNER_LINES:
        print(line)
    print(f" python sdk: {version.lower()}")
    print(" visit firmngin.dev/docs for more")
    print()


__all__ = ["print_startup_banner"]
