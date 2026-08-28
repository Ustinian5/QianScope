from __future__ import annotations

import hashlib

import numpy as np

from echo_swm.agents.policy import ActionDistribution, AgentObservation
from echo_swm.contracts.person import DynamicAgentState


class StatisticalPolicy:
    def act(
        self,
        state: DynamicAgentState,
        observation: AgentObservation,
        action_space: list[str],
    ) -> ActionDistribution:
        if not action_space:
            raise ValueError("action_space must not be empty")
        scores = np.ones(len(action_space), dtype=float) * 0.2
        for index, action in enumerate(action_space):
            if action in {"share", "comment", "oppose", "support"}:
                scores[index] += observation.exposure_strength * state.expression_intent
            if action == "purchase":
                scores[index] += state.purchase_intent
            if action in {"ignore", "abstain"}:
                scores[index] += 1 - state.action_readiness
        probabilities = scores / scores.sum()
        digest = hashlib.sha256(
            f"{state.agent_id}:{state.snapshot_id}:{','.join(action_space)}".encode()
        ).digest()
        uniform = int.from_bytes(digest[:8], "big") / (2**64 - 1)
        selected = action_space[
            int(np.searchsorted(np.cumsum(probabilities), uniform, side="right"))
        ]
        return ActionDistribution(
            action_probabilities=dict(zip(action_space, probabilities.tolist(), strict=True)),
            selected_action=selected,
            content_stance=observation.neighbor_stance,
            confidence=float(1 - state.state_uncertainty.get("action", 0.5)),
            reason_codes=["STATISTICAL_POLICY", "OBSERVED_EXPOSURE"],
            evidence_ids=observation.evidence_ids,
        )
