from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from echo_swm.core.ids import stable_hash


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scenario_id: str
    root_seed: int
    model_version: str
    data_version: str
    graph_version: str
    prompt_version: str = "prompts-v1"
    config_hash: str
    input_hash: str
    output_hash: str
    python_version: str = Field(default_factory=platform.python_version)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")

    @classmethod
    def read(cls, path: Path) -> RunManifest:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def verify(self, *, config: Any, inputs: Any, outputs: Any) -> dict[str, bool]:
        return {
            "config_hash": self.config_hash == stable_hash(config),
            "input_hash": self.input_hash == stable_hash(inputs),
            "output_hash": self.output_hash == stable_hash(outputs),
        }


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True, default=str) + "\n")
