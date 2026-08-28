from __future__ import annotations

from typer import Typer

from qianscope import DISCLAIMER, __version__
from qianscope.cli import app


def test_canonical_package_exports_public_identity() -> None:
    assert __version__ == "0.1.0"
    assert "概率模拟" in DISCLAIMER
    assert isinstance(app, Typer)
