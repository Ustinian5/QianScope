# Implementation backlog

> 本文件记录旧架构的技术缺口。2026-08-24 之后的产品优先级和里程碑以
> [`PRODUCT_REQUIREMENTS.md`](PRODUCT_REQUIREMENTS.md) 为准；未进入该文档 M1–M6
> 的任务不得优先于人格 Agent、问卷预测、通用事件运行时和极简前端。

The executable questionnaire product now covers M1-M5 at P0: unified contracts, a stable 5,000
personality population, exact runtime tiers, multiplex propagation, six question types,
baseline/post-event prediction, 30+ tick baseline/event/alternative paths, group differences,
uncertainty, replay, export, outcome backfill, P0 API, CLI, and a five-step frontend. The M6
infrastructure now includes authorized aggregate population-margin ingestion, IPF diagnostics,
historical questionnaire/event-result contracts, leakage-safe temporal holdouts, calibration
promotion gates, backfill records, and optional five-step UI uploads. Real-world validation remains
open because the repository intentionally ships no licensed population or outcome dataset.

The following are intentionally not claimed as complete:

- The built-in personality population is synthetic. Authorized margins can now constrain its
  aggregate weights, but real-population claims still require provenance review, nonresponse/frame
  diagnostics, and external validation.
- Generic questionnaire and event probabilities can now use versioned temporal calibration, but
  remain uncalibrated until actual authorized panels/outcomes are supplied and the holdout gate
  passes.
- Open responses are structured simulated themes and clearly labeled representative text. Richer
  key-agent language generation may use the constrained LLM adapter, but must not be presented as
  real respondent quotes or hidden chain-of-thought.

- Event-forecast base rates and rule weights in the executable example are synthetic. Real-domain
  claims require immutable historical forecasts, fixed event-resolution labels, rolling temporal
  holdouts, calibration by event/horizon/regime, and candidate-recall evaluation.
- The Suzhou profile uses official aggregates but synthetic micro records and explicit mechanism
  assumptions. Policy use requires authorized district demographics, observed OD/service usage,
  historical event panels, survey calibration, temporal holdouts, and external validation.
- Real-data harmonization connectors and ontology mapping require licensed input schemas and governance approval. Contracts exist; validation requires a supplied dataset and data card.
- Entropy balancing, TRS integerization, k-prototypes, DCSBM, hypergraph attention, Ray, PostgreSQL/S3, MLflow, and OpenTelemetry are scale/production adapters. Local interfaces are stable; benchmarks and deployment requirements are needed.
- Causal estimates for observational data require propensity/common-support diagnostics and defensible covariates. The synthetic randomized experiment is the only causal demo.
- PyTorch table transformers, temporal GNNs, JEPA/latent transitions, deep ensembles, conformal prediction, survival heads, and distillation require training datasets and blind comparisons. `WorldModel` is the integration interface.
- Calibration promotion is automatic only for the current overall Brier/log-loss non-regression
  gate. Subgroup, horizon, interval-coverage, drift, and external blind-test gates require real
  observation history before they can be enforced.
- Authentication, field-level access control, deletion orchestration, differential privacy, and jurisdiction-specific retention are deployment responsibilities and require an identity/storage system.

No placeholder methods are used for these items; they are absent rather than reported as finished.
