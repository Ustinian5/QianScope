# ADR 0005: Unified Human Digital Twin social-world runtime

- Status: Accepted
- Date: 2026-08-25

## Context

The repository had separate questionnaire, city, price, and hazard runtimes. Personality was only a partial flat feature set, while the general event state used scalar belief and emotion values. This could not provide the location-aware, channel-aware and inspectable event diffusion expected by the target demo.

## Decision

Add a clean-room `echo_swm.world` runtime that reuses the stable research population but expands it to a complete structured personality architecture. Keep immutable personality/value vectors separate from mutable beliefs, goals, mental state, memories, and relationship trust. Execute one deterministic batched transition order for every tier, with locations and events as first-class entities. Persist weighted profiles, relationships, locations, trajectories, traces, snapshots, replay chains and a run manifest.

The world runtime is API- and map-provider-independent. It represents a large population through weighted synthetic prototypes and never claims those prototypes are real residents.

## Consequences

- The frontend can implement map, timeline, population and event views against stable contracts.
- Existing questionnaire, city and event-forecast APIs remain compatible.
- Personality cannot be mutated by an event without replay verification failing.
- Real-world accuracy remains contingent on authorized data and out-of-sample calibration.
