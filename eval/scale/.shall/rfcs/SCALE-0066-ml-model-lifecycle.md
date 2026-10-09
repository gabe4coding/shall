---
id: SCALE-0066
title: Machine learning model lifecycle
status: draft
domain: ml
artifacts: [diff, code, spec, doc]
languages: [any]
owner: data-science
review_by: 2027-06-30
supersedes: []
summary: >
  Reproducible training, honest evaluation, bias checks, registration and production
  monitoring of machine learning models such as ranking and no-show prediction.
applies_when: >
  The content trains, evaluates, registers, deploys or monitors a machine learning model,
  defines model features, or describes such a model.
not_applies_when: >
  No machine learning model or model feature is trained, evaluated, served or described.
---

# SCALE-0066: Machine learning model lifecycle

## Context

Models for restaurant ranking, no-show prediction and dynamic pricing change what diners
see and what restaurants earn. Models that cannot be retrained to the same result, or
that were evaluated on the data they learned from, cannot be trusted or debugged.
Features computed one way in training and another way in serving are a common silent
failure.

## Requirements

### SCALE-0066.1 Reproducible training runs
A training job MUST record the code commit, the dataset snapshot id, the hyperparameters
and the random seeds, so that the run can be repeated to the same metrics.

- Applies when: the content adds or changes a model training script, notebook, pipeline step or training configuration.
- Enforcement: agent

### SCALE-0066.2 Pinned training dependencies
Training environments MUST pin exact versions of ML libraries (for example scikit-learn,
XGBoost, PyTorch) in a lock file or container image digest.

- Applies when: the content adds or changes the dependency file, lock file or image of a training job.
- Enforcement: linter

### SCALE-0066.3 Held-out evaluation
Model metrics used to approve a model MUST be computed on a held-out test set that was
not used for training or tuning, split by time for forecasting and ranking models.

- Applies when: the content splits data into train, validation and test sets, or computes metrics to compare or approve a model.
- Enforcement: agent

### SCALE-0066.4 Baseline comparison
An evaluation SHOULD compare the new model against the current production model and a
simple baseline on the same test set.

- Applies when: the content reports offline evaluation metrics of a model.
- Enforcement: agent

### SCALE-0066.5 Bias checks by segment
Evaluation of a model that ranks restaurants or scores diners MUST report metrics per
segment (country, city size, restaurant price range, new versus established restaurants)
and flag segments that are more than 10% worse than the overall metric.

- Applies when: the content evaluates a ranking, recommendation, scoring or pricing model that affects diners or restaurants.
- Enforcement: agent

### SCALE-0066.6 Registered models only
Production serving MUST NOT load a model that is not registered in the model registry
with its metrics, training run id and an approved status.

- Applies when: the content deploys, loads or serves a model artifact, or changes the model version used in production.
- Enforcement: agent

### SCALE-0066.7 Features from the feature store
Features used by a production model SHOULD be read from the feature store in both
training and serving, instead of being computed by separate code in each.

- Applies when: the content defines, computes or reads model features in a training pipeline or an online serving path.
- Enforcement: agent

### SCALE-0066.8 Drift monitoring
A production model MUST have monitoring of input feature drift and prediction
distribution, with an alert to the owning team when drift exceeds a set threshold.

- Applies when: the content deploys a new model to production or describes how a production model is monitored.
- Enforcement: agent

### SCALE-0066.9 Model card
A model promoted to production SHOULD have a model card that states its purpose,
training data, known limitations and intended use.

- Applies when: the content registers, promotes or documents a model for production.
- Artifacts: doc, spec
- Enforcement: agent

### SCALE-0066.10 Shadow deployment
A new model version MAY run in shadow mode next to the production model, logging its
predictions without serving them, before a live A/B test.

- Applies when: the content describes or configures the rollout of a new model version.
- Enforcement: agent
