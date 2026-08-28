# Event Forecasting Runtime

## 1. Product boundary

The event runtime predicts a finite set of explicitly defined candidate events, conditional on the information available at a declared cutoff. A forecast is not an unconstrained statement about everything that might happen. Candidate generation, base-rate quality, signal availability, model calibration, and world-state quality are separate sources of error and are reported separately.

The city runtime is one possible provider of world-state metrics. Market, organization, supply-chain, policy, reputation, public-health, and other domains can provide different adapters while keeping the same `EventForecastQuery -> EventForecastResult` contract.

## 2. Hazard model

For candidate event `e`, path `k`, and future day `t`, the engine calculates:

```text
logit(h[e,k,t]) = logit(base_daily_hazard[e])
                  + path_uncertainty[e,k]
                  + decayed_known_signal_evidence[e,t]
                  + state_threshold_effects[e,k,t]
                  + parent_event_lag_effects[e,k,t]
                  + intervention_effects[e,t]
```

The engine samples the first occurrence using a common uniform random tensor shared by all counterfactual branches. Each candidate can first occur once within its allowed window. Once an event occurs, its sampled impacts update world metrics and decay with explicit half-lives. Updated metrics can activate downstream state conditions.

Signal evidence uses only observations whose `available_at <= as_of`. A known signal contribution decays exponentially from the prediction cutoff. Parent events operate only inside explicit minimum/maximum lag windows, also with exponential decay.

## 3. Outputs

For every branch and candidate:

- first-occurrence and cumulative probability by day;
- probability of occurrence within the full horizon;
- conditional time-to-event P10/P50/P90, mean, and standard deviation;
- conditional severity distribution;
- leading signal contributions in log-odds units;
- base-rate origin and out-of-distribution flag.

For every branch:

- final world-metric delta distributions;
- most common non-empty event sequences;
- expected configured intervention cost.

For every non-control branch, the result reports event-probability deltas against the first branch. These deltas use common random numbers but remain model-based counterfactuals rather than identified causal effects.

## 4. Candidate generation and LLM boundary

An OpenAI-compatible model may compile natural language into a typed query. Its responsibilities are candidate enumeration, explicit assumptions, ontology normalization, and rule construction. It is forbidden by prompt and schema from returning final probabilities. The numerical engine calculates all paths and distributions.

In production, candidate recall should be evaluated separately from probability calibration. Candidate omission can dominate total forecast error even when conditional probabilities are well calibrated.

## 5. Calibration lifecycle

The default example is deliberately marked `prior_predictive_uncalibrated`. A production promotion requires:

1. forecasts persisted before outcomes are known;
2. immutable prediction cutoffs and signal availability timestamps;
3. event-resolution rules fixed before evaluation;
4. walk-forward or rolling-origin temporal holdouts;
5. Brier, Brier Skill, Log Loss, ECE, coverage, and lead-time reports;
6. calibration analysis by event type, horizon, geography, severity, and data regime;
7. comparison against climatology/base-rate and simple trend baselines;
8. explicit monitoring for candidate-set drift and base-rate drift.

`POST /v1/event-forecasts/backtest` and `qianscope event backtest` score resolved binary event forecasts. They do not automatically promote a model.

## 6. Replay and provenance

Each run persists:

- the complete query inside `forecast.json`;
- per-day curves in `probability_curves.csv`;
- sampled occurrence days, severities, and final metrics in `event_paths.npz`;
- daily aggregate counts and record hashes in `replay.jsonl`;
- query, seed, dimensions, model version, forecast hash, and path-file SHA-256 in `run_manifest.json`.

Replay verification checks every daily record hash, expected record count, and the full path artifact hash.

## 7. Known limitations

- The current engine uses discrete daily time and first occurrence rather than continuous-time or recurrent events.
- Base rates and rule weights are supplied by data adapters, historical estimation, or explicit priors; the demo values are synthetic.
- Event impacts are state deltas with exponential decay, not structural causal estimates.
- Correlation is represented through shared signals, state feedback, parent events, and path uncertainty; there is no learned latent copula in v1.
- Accurate real-world forecasting requires authorized historical panels and stable event-resolution labels.
