"""Shared pytest configuration: make the OCF tooling importable."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def sample_function_path() -> Path:
    return Path(__file__).parent / "fixtures" / "function-sample.yaml"


@pytest.fixture()
def sample_background_path() -> Path:
    return Path(__file__).parent / "fixtures" / "background-sample.yaml"
