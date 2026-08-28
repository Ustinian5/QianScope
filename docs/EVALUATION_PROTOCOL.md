# Evaluation protocol

The executable demo uses a respondent-held-out split and reports accuracy, macro-F1, AUROC, log loss, Brier score, and expected calibration error. Training-set metrics are not reported. Known counterfactual probabilities from the synthetic mechanism are used only after inference for model error measurement.

Production evaluation must add temporal, rolling-origin, entity, cross-region, cross-survey, and cross-domain splits; subgroup calibration and worst-group error; placebo tests; CATE diagnostics; trajectory error; and pre-registered blind historical tests.
