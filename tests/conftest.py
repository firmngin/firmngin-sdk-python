"""Shared test fixtures and configuration for the firmngin test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"
KEYS_EXAMPLE = REPO_ROOT / "keys.json.example"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Absolute path to the tests/fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def keys_example_path() -> Path:
    """Absolute path to keys.json.example — used to smoke-test KeysConfig parsing."""
    return KEYS_EXAMPLE
