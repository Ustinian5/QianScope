# QianScope Architecture

> 本系统是基于公开研究路线自主实现的社会世界模型，不代表任何第三方公司的内部实现。

## 1. Executable product paths

The questionnaire product is a questionnaire-driven general event prediction workflow. A user describes
an event, selects a target population, creates or imports a questionnaire, confirms time and
scenario assumptions, and receives a result ordered for decision reading rather than model
inspection.

The executable primary path is:

```text
stable 5,000-agent personality population
  -> optional authorized aggregate margins and run-scoped raking
  -> multiplex relationship graph
  -> baseline / described event / alternatives
  -> 30+ observe-decide-act-remember ticks on every agent
  -> per-agent baseline and post-event questionnaire probabilities
  -> weighted total, group differences, trajectories and uncertainty
  -> optional leakage-safe historical calibration with temporal holdout gate
  -> replay, export and outcome backfill
```

The detailed implementation is in [`RESEARCH_PREDICTION.md`](RESEARCH_PREDICTION.md). The hazard
event engine, Suzhou world adapter, and price experiment remain supporting research modules rather
than the default product navigation.

The repository also exposes a unified Human Digital Twin social-world backend for city/campus
event simulation. It combines complete structured personality vectors, mutable beliefs/goals/
mental state, three-layer memory, six relationship types, hierarchical locations, daily mobility,
six propagation channels, agent/location drilldown, snapshots and deterministic replay. This path
is intentionally independent of AMap, 3D assets or any frontend provider. See
[`HUMAN_DIGITAL_TWIN_SOCIAL_WORLD.md`](HUMAN_DIGITAL_TWIN_SOCIAL_WORLD.md).

## 2. System boundary

QianScope predicts conditional probability distributions over questionnaire responses, aggregate
reactions, generic downstream events, and short-horizon trajectories. It does not claim to
reproduce a real person's thoughts or guarantee real-world outcomes. The current primary executable
is the questionnaire-driven general event runtime; the synthetic randomized price intervention is
retained as a legacy validation slice with known synthetic ground truth.

The system is organized into five planes:

1. **Data plane** validates typed manifests, people, events, questions, observations, and availability times.
2. **Population plane** weights prototype people, performs IPF/raking, and constructs bounded synthetic graphs.
3. **Model plane** provides weighted statistical baselines, event-conditioned transitions, calibration, and a stable world-model interface.
4. **Simulation plane** runs deterministic batched state records, location mobility, event/channel propagation, counterfactual branches, snapshots, and replay. An agent is data plus policy, memory, and relationships—not a process.
5. **Serving and governance plane** exposes FastAPI and CLI entry points, run manifests, audit logs, model cards, privacy limits, and promotion gates.

The Suzhou profile extends these planes into a coupled city runtime: official aggregate anchors,
weighted synthetic residents and households, institutions, a spatial employment-gravity/OD layer,
a four-layer social graph, exogenous events, policy branches, and K-path uncertainty aggregation.
The detailed design and provenance are in `docs/SUZHOU_CITY_MODEL.md`.

The questionnaire runtime is the primary cross-domain product. The lower-level hazard engine can
still consume timestamped signals, candidate-specific base hazards, parent-event lag rules, and
counterfactual branches when an advanced adapter supplies those contracts. World profiles such as
Suzhou are optional adapters, not the core product boundary. See `docs/EVENT_FORECASTING.md`.

## 3. Legacy executable vertical slice

```text
Synthetic pre-survey (known mechanism)
  -> temporal/respondent split
  -> weighted baseline training
  -> calibrated individual probabilities
  -> weighted population/segment distributions
  -> control / +30% / +30% with student discount branches
  -> 14-day constrained diffusion
  -> evaluation, reports, manifest, snapshot and replay
```

Ground-truth outcome columns are kept outside inference feature builders. All times carry `observed_at`, `available_at`, and a prediction cutoff so the leakage scanner can reject future data.

## 4. Model runtime

`ECHOModel` remains the legacy internal model-class name. QianScope's first implementation combines structured feature encoders, weighted logistic baselines, event effects, bootstrap uncertainty, and probability calibration. It can operate with no LLM.

The LLM adapter is OpenAI-compatible and optional. It is used only for typed event normalization and high-uncertainty/key-agent policies. Calls are budgeted, cached, logged, JSON-validated, and never silently replaced with random output. Supplying `QIANSCOPE_LLM_API_KEY`, `QIANSCOPE_LLM_BASE_URL`, and `QIANSCOPE_LLM_MODEL` enables it without changing application code; legacy `ECHO_*` names remain accepted.

## 5. Runtime tiers

- Key agents: 50 high-influence nodes with lower decision noise and deeper deliberation.
- Representative agents: 450 nodes covering main population groups with intermediate policy depth.
- Background population: at least 4,500 vectorized statistical agents preserving scale and tails.

All tiers actually execute observe, decide, act, and remember at every tick. Simulation is batched;
no per-agent resident processes are created.

## 6. Determinism and replay

Every run records input/config/model/data/prompt hashes, a root seed, branch seed derivations, dependency versions, and output hashes. Counterfactual branches inherit the same starting snapshot and common-random-number stream. External LLM responses are recorded in a content-addressed cache for offline replay.

## 7. Storage

The local profile uses Parquet for analytical data and JSON/JSONL for metadata, events, and replay. Storage adapters isolate filesystem access so PostgreSQL and S3/MinIO can be added without changing model contracts. Local operation does not require Docker, Ray, a vector database, or an LLM key.

## 8. Safety boundary

Only licensed, authorized, consented, de-identified, aggregate, or synthetic data is allowed. Individual outputs are probabilistic and cannot be used for high-risk decisions, re-identification, discrimination, or covert psychological targeting. Aggregate reports suppress cells smaller than the configured minimum.

## 9. Versioning

Data, population margins, calibration profiles, model, prompt, scenario, and schema versions are
independent. Reality observations are append-only. The questionnaire runtime automatically applies
a calibration profile only after temporal-holdout Brier and log-loss non-regression; broader
subgroup, drift, coverage, and external-validation gates remain required before real-world claims.
