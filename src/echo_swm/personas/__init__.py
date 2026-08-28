"""Stable synthetic persona contracts with lazy catalog exports."""

from typing import Any

from echo_swm.personas.contracts import (
    PersonaInterviewRequest,
    PersonaInterviewResponse,
    PersonaMapSnapshot,
    PersonaProfile,
    PersonaSearchResult,
)


def __getattr__(name: str) -> Any:
    if name in {"DATA_VERSION", "MODEL_VERSION", "PersonaCatalog"}:
        from echo_swm.personas import catalog

        return getattr(catalog, name)
    raise AttributeError(name)


__all__ = [
    "DATA_VERSION",
    "MODEL_VERSION",
    "PersonaCatalog",
    "PersonaInterviewRequest",
    "PersonaInterviewResponse",
    "PersonaMapSnapshot",
    "PersonaProfile",
    "PersonaSearchResult",
]
