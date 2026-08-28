from __future__ import annotations

import hashlib

import numpy as np


def derive_seed(root_seed: int, namespace: str) -> int:
    digest = hashlib.sha256(f"{root_seed}:{namespace}".encode()).digest()
    return int.from_bytes(digest[:4], "big")


def rng_for(root_seed: int, namespace: str) -> np.random.Generator:
    return np.random.default_rng(derive_seed(root_seed, namespace))
