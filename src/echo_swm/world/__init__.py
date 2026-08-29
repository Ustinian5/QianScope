"""Location-aware Human Digital Twin social-world runtime.

Engine exports are loaded lazily so persona definitions can safely import world constants.
"""

from typing import Any

from echo_swm.world.contracts import (
    WorldEvent,
    WorldSimulationRequest,
    WorldSimulationResult,
    WorldSpec,
)

_ENGINE_EXPORTS = {
    "get_world_agent",
    "get_world_location",
    "load_world_simulation",
    "run_world_simulation",
    "search_world_agents",
    "verify_world_replay",
}


def __getattr__(name: str) -> Any:
    if name in _ENGINE_EXPORTS:
        from echo_swm.world import engine

        return getattr(engine, name)
    raise AttributeError(name)


__all__ = [
    "WorldEvent",
    "WorldSimulationRequest",
    "WorldSimulationResult",
    "WorldSpec",
    "get_world_agent",
    "get_world_location",
    "load_world_simulation",
    "run_world_simulation",
    "search_world_agents",
    "verify_world_replay",
]
