from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from echo_swm.core.ids import stable_hash


@dataclass(frozen=True)
class Snapshot:
    branch: str
    tick: int
    awareness: NDArray[np.float64]
    negative_expression: NDArray[np.float64]
    purchase_intent: NDArray[np.float64]
    trust: NDArray[np.float64]

    @property
    def content_hash(self) -> str:
        return stable_hash(
            {
                "branch": self.branch,
                "tick": self.tick,
                "awareness": self.awareness.tolist(),
                "negative_expression": self.negative_expression.tolist(),
                "purchase_intent": self.purchase_intent.tolist(),
                "trust": self.trust.tolist(),
            }
        )


class SnapshotStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, snapshot: Snapshot) -> Path:
        branch_dir = self.root / snapshot.branch
        branch_dir.mkdir(parents=True, exist_ok=True)
        path = branch_dir / f"tick_{snapshot.tick:03d}.npz"
        np.savez_compressed(
            path,
            awareness=snapshot.awareness,
            negative_expression=snapshot.negative_expression,
            purchase_intent=snapshot.purchase_intent,
            trust=snapshot.trust,
            content_hash=np.asarray(snapshot.content_hash),
        )
        return path

    def load(self, branch: str, tick: int) -> Snapshot:
        path = self.root / branch / f"tick_{tick:03d}.npz"
        with np.load(path) as payload:
            snapshot = Snapshot(
                branch=branch,
                tick=tick,
                awareness=payload["awareness"],
                negative_expression=payload["negative_expression"],
                purchase_intent=payload["purchase_intent"],
                trust=payload["trust"],
            )
            if str(payload["content_hash"].item()) != snapshot.content_hash:
                raise ValueError("snapshot content hash mismatch")
            return snapshot
