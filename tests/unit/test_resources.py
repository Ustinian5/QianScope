from __future__ import annotations

from pathlib import Path

import pytest

from echo_swm.core.resources import resolve_project_resource


def test_resolve_project_resource_uses_configured_runtime_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    resource = tmp_path / "scenarios" / "event.json"
    resource.parent.mkdir()
    resource.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("QIANSCOPE_RESOURCE_ROOT", str(tmp_path))

    resolved = resolve_project_resource(
        "scenarios/event.json",
        module_file=__file__,
    )

    assert resolved == resource.resolve()


def test_resolve_project_resource_falls_back_to_working_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    resource = tmp_path / "configs" / "city.json"
    resource.parent.mkdir()
    resource.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("QIANSCOPE_RESOURCE_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    resolved = resolve_project_resource(
        "configs/city.json",
        module_file=__file__,
    )

    assert resolved == resource.resolve()
