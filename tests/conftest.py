"""Shared fixtures. Every test runs against its own bookman config."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from bookman import Library, NullSource

import mock_library


@pytest.fixture(autouse=True)
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point bookman at a config file in `tmp_path` that doesn't exist yet,
    and the TUI's prefs likewise, and clear `$BOOKMAN_LIBRARY`, so no test
    sees the user's real library or settings."""
    config = tmp_path / "config" / "config.json"
    monkeypatch.setenv("BOOKMAN_CONFIG", str(config))
    monkeypatch.setenv("BOOKMAN_TUI_PREFS", str(tmp_path / "prefs" / "prefs.json"))
    monkeypatch.delenv("BOOKMAN_LIBRARY", raising=False)
    return config


@pytest.fixture
def empty_library(tmp_path: Path) -> Path:
    """An existing, empty bookman library."""
    root = tmp_path / "library"
    Library(root, source=NullSource())
    return root


@pytest.fixture(scope="session")
def mock_library_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The mock library (tools/mock_library.py), built once per session."""
    root = tmp_path_factory.mktemp("mock") / "library"
    mock_library.build(root)
    return root


@pytest.fixture
def mock_root(mock_library_template: Path, tmp_path: Path) -> Path:
    """A fresh copy of the mock library for one test to change freely."""
    root = tmp_path / "mock-library"
    shutil.copytree(mock_library_template, root)
    return root
