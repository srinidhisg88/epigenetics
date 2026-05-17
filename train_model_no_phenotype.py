"""
No-Phenotype Model Training for Epilepsy Variant Classification
===============================================================
Trains an isotonic-calibrated XGBoost classifier on 93 engineered
features derived solely from variant annotations — no phenotype
strings are used anywhere in this pipeline.

Pipeline:
  1. Load pre-engineered no-phenotype feature matrices
  2. Apply SMOTETomek to the training fold only
  3. Fit XGBoost + isotonic calibration (CalibratedClassifierCV)
  4. Evaluate on validation and held-out test folds
  5. Save model, gene statistics, and performance metadata

Output:
  models/epilepsy_classifier_no_phenotype.pkl
  models/performance_no_phenotype.json
  data/processed/gene_statistics.json
"""

import json
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from imblearn.combine import SMOTETomek
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (
    accuracy_score, brier_score_loss, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score,
)
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

print("=" * 70)
print("NO-PHENOTYPE EPILEPSY VARIANT CLASSIFIER — TRAINING")
print("=" * 70)

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
print("\n[1] Loading feature matrices...")

X_train = pd.read_csv(DATA_PROCESSED / "X_train_no_phenotype.csv")
X_val   = pd.read_csv(DATA_PROCESSED / "X_val_no_phenotype.csv")
X_test  = pd.read_csv(DATA_PROCESSED / "X_test_no_phenotype.csv")

train_df = pd.read_csv(DATA_PROCESSED / "train.csv")
val_df   = pd.read_csv(DATA_PROCESSED / "val.csv")
test_df  = pd.read_csv(DATA_PROCESSED / "test.csv")

y_train = train_df["Label"]
y_val   = val_df["Label"]
y_test  = test_df["Label"]

print(f"    X_train : {X_train.shape}  |  pathogenic: {y_train.sum():,}")
print(f"    X_val   : {X_val.shape}")
print(f"    X_test  : {X_test.shape}")

# ---------------------------------------------------------------------------
# 2. Gene statistics (used at inference time)
# ---------------------------------------------------------------------------
print("\n[2] Computing gene statistics from training fold...")

gene_stats = (
    train_df.groupby("GeneSymbol")["Label"]
    .agg(pathogenic_rate="mean", sample_count="count")
    .reset_index()
)
gene_statistics = {
    row["GeneSymbol"]: {
        "pathogenic_rate": round(row["pathogenic_rate"], 6),
        "sample_count": int(row["sample_count"]),
    }
    for _, row in gene_stats.iterrows()
}
gene_stats_path = DATA_PROCESSED / "gene_statistics.json"
with open(gene_stats_path, "w") as f:
    json.dump(gene_statistics, f, indent=2)
print(f"    Saved → {gene_stats_path}")

# ---------------------------------------------------------------------------
# 3. SMOTETomek resampling (training fold only)
# ---------------------------------------------------------------------------
print("\n[3] Applying SMOTETomek resampling...")

smote_tomek = SMOTETomek(random_state=42, n_jobs=-1)
X_train_res, y_train_res = smote_tomek.fit_resample(X_train, y_train)

print(f"    Before: {len(X_train):,} samples  →  After: {len(X_train_res):,} samples")
print(f"    Pathogenic after: {y_train_res.sum():,} | Benign: {(y_train_res == 0).sum():,}")

# ---------------------------------------------------------------------------
# 4. Train XGBoost + isotonic calibration
# ---------------------------------------------------------------------------
print("\n[4] Training XGBoost with isotonic calibration...")

xgb = XGBClassifier(
    n_estimators=300,
    max_depth=8,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_weight=3,
    gamma=0.1,
    reg_alpha=0.1,
    reg_lambda=1.0,
    objective="binary:logistic",
    eval_metric="logloss",
    random_state=42,
    n_jobs=-1,
    verbosity=0,
)

model = CalibratedClassifierCV(xgb, method="isotonic", cv=5)
model.fit(X_train_res, y_train_res)
print("    Training complete.")

# ---------------------------------------------------------------------------
# 5. Evaluation helper
# ---------------------------------------------------------------------------

def evaluate(model, X, y, label):
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
    metrics = {
        "accuracy":    round(accuracy_score(y, y_pred),    6),
        "precision":   round(precision_score(y, y_pred),   6),
        "recall":      round(recall_score(y, y_pred),      6),
        "f1_score":    round(f1_score(y, y_pred),          6),
        "roc_auc":     round(roc_auc_score(y, y_prob),     6),
        "brier_score": round(brier_score_loss(y, y_prob),  6),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp),
                             "fn": int(fn), "tp": int(tp)},
        "specificity": round(tn / (tn + fp), 6),
        "sensitivity": round(tp / (tp + fn), 6),
    }
    print(f"\n    [{label}]")
    print(f"      Accuracy : {metrics['accuracy']:.4f}  |  AUC : {metrics['roc_auc']:.4f}")
    print(f"      F1       : {metrics['f1_score']:.4f}  |  Brier: {metrics['brier_score']:.4f}")
    print(f"      Confusion: TN={tn} FP={fp} FN={fn} TP={tp}")
    return metrics

print("\n[5] Evaluating model...")
train_metrics = evaluate(model, X_train, y_train, "Train")
val_metrics   = evaluate(model, X_val,   y_val,   "Validation")
test_metrics  = evaluate(model, X_test,  y_test,  "Test")

# ---------------------------------------------------------------------------
# 6. Feature importance (from underlying XGBoost estimator)
# ---------------------------------------------------------------------------
base_xgb = model.calibrated_classifiers_[0].estimator
importances = base_xgb.feature_importances_
feature_importance = sorted(
    zip(X_train.columns.tolist(), importances),
    key=lambda x: x[1],
    reverse=True,
)
top_features = [
    {"feature": name, "importance": round(float(imp), 8)}
    for name, imp in feature_importance[:20]
]

# ---------------------------------------------------------------------------
# 7. Save model and metadata
# ---------------------------------------------------------------------------
print("\n[6] Saving artefacts...")

model_path = MODELS_DIR / "epilepsy_classifier_no_phenotype.pkl"
joblib.dump(model, model_path)
print(f"    Model → {model_path}")

performance = {
    "model_name": "epilepsy_classifier_no_phenotype",
    "training_date": datetime.now().isoformat(),
    "uses_phenotype_features": False,
    "num_features": X_train.shape[1],
    "training_samples": {
        "original": len(X_train),
        "after_smote": len(X_train_res),
    },
    "metrics": {
        "train":      train_metrics,
        "validation": val_metrics,
        "test":       test_metrics,
    },
    "top_features": top_features,
}

perf_path = MODELS_DIR / "performance_no_phenotype.json"
with open(perf_path, "w") as f:
    json.dump(performance, f, indent=2)
print(f"    Metrics → {perf_path}")

print("\n" + "=" * 70)
print("DONE. Model saved to:", model_path)
print("=" * 70)
