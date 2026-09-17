# Model Card - Credit Default Baseline

> Template per syllabus Assignment 1 (model card is a fixed rubric item).

## Overview
- **Task:** Binary classification - probability of default.
- **Baseline:** Logistic regression (transparent).  **Challenger:** XGBoost.
- **Version:** baseline-0.1.0-stub

## Data
- Source, window, and **time split** (no look-ahead).  See `notebooks/prework_A`.

## Evaluation
- AUC, calibration, threshold sweep, **confusion-cost matrix**.
- Statistical performance vs **economic usefulness** (expected loss).

## Risks / pathologies
- Non-stationarity, regime change, survivorship/look-ahead bias,
  leakage, missingness, class imbalance, low SNR, correlated features.

## Intended use / limits
- Decision-support tool orchestrated by agents; **software enforces policy**.
