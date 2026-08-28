# ADR 0003: Verified baseline before latent complexity

- Status: Accepted
- Date: 2026-08-24

## Decision

The first `ECHOModel` uses structured encoders, survey-weighted logistic models, event features, calibration, and bootstrap intervals. Majority, weighted prevalence, segment mean, event ablations, and uncalibrated variants are evaluated alongside it.

## Consequences

Performance and cost have honest reference points. PyTorch latent transitions remain behind a future adapter and will not become the default until blind evaluation beats these baselines.
