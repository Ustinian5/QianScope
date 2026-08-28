# ADR 0002: Typed, time-aware data contracts

- Status: Accepted
- Date: 2026-08-24

## Decision

Use Pydantic v2 contracts at all service and storage boundaries. Observations distinguish observed, inferred, missing, synthetic, and model-generated values. `occurred_at`, `observed_at`, `available_at`, and `prediction_cutoff` are separate concepts.

## Consequences

Invalid probabilities, negative weights, inverted time ranges, unknown scenario actions, and future-available features fail early. Business modules receive typed models rather than unconstrained dictionaries.
