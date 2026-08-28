# Model

The first verified `ECHOModel` is a structured, event-conditioned probability model. It encodes numeric/categorical population attributes directly, not by stringifying a persona. Five survey/behavior heads use survey-weighted logistic models. A respondent split reserves 60% for fitting, 20% for temperature calibration, and 20% for final reporting.

The full model is compared with weighted prevalence, uncalibrated, and event-ablated baselines. Later PyTorch person/event/question encoders and latent transitions must retain the same `WorldBatch -> WorldForecast` contract and beat the simple baseline in blind tests before promotion.

The cross-domain event runtime is a separate model surface. It represents candidate occurrence as
a discrete-time hazard conditioned on timestamped signals, current world metrics, parent-event lag
windows, and interventions. Monte Carlo paths produce cumulative occurrence probabilities,
conditional event times, severities, event chains, and impact distributions. Its default scenario
is an explicit prior-predictive example and remains uncalibrated until resolved historical
forecasts pass rolling temporal evaluation. See `docs/EVENT_FORECASTING.md`.
