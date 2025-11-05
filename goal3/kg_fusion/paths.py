"""Shared path helpers for the KG fusion stack."""
from __future__ import annotations

import os
from pathlib import Path

from . import PACKAGE_ROOT


DATA_ROOT = PACKAGE_ROOT / "data"
DOCS_ROOT = PACKAGE_ROOT / "docs"
EVAL_ROOT = PACKAGE_ROOT / "eval"
SCRIPTS_ROOT = PACKAGE_ROOT / "scripts"


def env_or_path(env_name: str, relative: Path) -> Path:
    """Resolve a path by environment override, otherwise fall back to `relative`."""
    value = os.getenv(env_name)
    if value:
        return Path(value)
    return relative


def data_path(*parts: str) -> Path:
    """Return a path under the bundled data directory."""
    return DATA_ROOT.joinpath(*parts)
