# ADR 0004: Batched deterministic simulation

- Status: Accepted
- Date: 2026-08-24

## Decision

Represent agents as immutable profile records plus mutable typed state, policy, memory references, and graph edges. Run ticks in vectorized batches. Derive branch RNG streams from a shared root seed and persist snapshots and hashes.

## Consequences

Ten thousand weighted states can be simulated locally without ten thousand processes. Branch comparisons have lower Monte Carlo noise, and a run can be inspected or replayed. LLM nondeterminism is isolated behind recorded adapter calls.
