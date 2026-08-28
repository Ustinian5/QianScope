# Model card: echo-structured-logit-v1

- Status: executable development baseline
- Inputs: structured synthetic person state and one of three price-intervention branches
- Outputs: calibrated probabilities for purchase, churn, complaint, recommendation, and high trust
- Training: survey-weighted logistic heads, respondent split, held-out temperature calibration
- Intended use: synthetic/offline research and application integration testing
- Excluded use: decisions about specific real people, re-identification, discrimination, covert persuasion, or guaranteed forecasting
- Primary limitation: the bundled model is trained entirely on a transparent synthetic mechanism and does not establish external validity

Actual metrics are generated at runtime in `artifacts/demo/model_evaluation.html` and are never hard-coded here.
