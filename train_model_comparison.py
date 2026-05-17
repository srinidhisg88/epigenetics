"""
Multi-Model Comparison Training Script
=======================================
Trains and evaluates all candidate architectures reported in Table 3
of the paper:

  Logistic Regression, Random Forest, Gradient Boosting,
  XGBoost (uncalibrated), SimpleNN, DeepNN_Dropout,
  ResidualNN, AttentionNN, WideDeepNN

Classical models (LR, RF, GBM, XGBoost) are reported on the
validation fold. Neural networks are reported on the held-out test
fold — matching the paper's table caption.

Outputs:
  models/model_performance.json          — classical model metrics
  models/neural_network_results.json     — NN metrics (all architectures)
  models/nn_comparison.csv              — NN summary table
  models/nn_scaler.pkl                  — StandardScaler fit on train fold
  models/best_nn_ResidualNN.pth         — best NN checkpoint (ResidualNN)
"""

import json
import random
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from imblearn.combine import SMOTETomek
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, f1_score, precision_score,
    recall_score, roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Global seed — ensures reproducible results across all frameworks
# ---------------------------------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.cuda.manual_seed_all(SEED)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent
DATA_PROCESSED = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"
MODELS_DIR.mkdir(exist_ok=True)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

print("=" * 70)
print("MULTI-MODEL COMPARISON — EPILEPSY VARIANT CLASSIFICATION")
print(f"Device: {DEVICE}")
print("=" * 70)

# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------
print("\n[1] Loading feature matrices (original 99 features — matches model_performance.json)...")

# The original comparison (Nov 2025) used X_train.csv (99 features).
# Switch to X_train_no_phenotype.csv (93 features) if reproducing Dec 2025 runs.
X_train = pd.read_csv(DATA_PROCESSED / "X_train.csv")
X_val   = pd.read_csv(DATA_PROCESSED / "X_val.csv")
X_test  = pd.read_csv(DATA_PROCESSED / "X_test.csv")

train_df = pd.read_csv(DATA_PROCESSED / "train.csv")
val_df   = pd.read_csv(DATA_PROCESSED / "val.csv")
test_df  = pd.read_csv(DATA_PROCESSED / "test.csv")

y_train = train_df["Label"].values
y_val   = val_df["Label"].values
y_test  = test_df["Label"].values

print(f"    Train : {X_train.shape}  |  pathogenic: {y_train.sum():,}")
print(f"    Val   : {X_val.shape}")
print(f"    Test  : {X_test.shape}")

# ---------------------------------------------------------------------------
# 2. SMOTETomek (training fold only)
# ---------------------------------------------------------------------------
print("\n[2] SMOTETomek resampling...")
smote_tomek = SMOTETomek(random_state=42, n_jobs=-1)
X_train_res, y_train_res = smote_tomek.fit_resample(X_train, y_train)
print(f"    {len(X_train):,} → {len(X_train_res):,} samples after resampling")

# ---------------------------------------------------------------------------
# 3. Evaluation helper (classical models)
# ---------------------------------------------------------------------------

def evaluate_sklearn(model, X, y):
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]
    return {
        "accuracy": round(accuracy_score(y, y_pred), 6),
        "precision": round(precision_score(y, y_pred, zero_division=0), 6),
        "recall": round(recall_score(y, y_pred), 6),
        "f1": round(f1_score(y, y_pred), 6),
        "auc_roc": round(roc_auc_score(y, y_prob), 6),
    }

# ---------------------------------------------------------------------------
# 4. Classical models — evaluated on VALIDATION fold (as in paper Table 3)
# ---------------------------------------------------------------------------
print("\n[3] Training classical models...")

classical_results = {}

# --- Logistic Regression ---
print("    Logistic Regression...", end=" ", flush=True)
lr = LogisticRegression(max_iter=1000, random_state=42, n_jobs=-1)
lr.fit(X_train_res, y_train_res)
classical_results["logistic_regression"] = evaluate_sklearn(lr, X_val, y_val)
joblib.dump(lr, MODELS_DIR / "logistic_regression.pkl")
print(f"acc={classical_results['logistic_regression']['accuracy']:.4f}  → saved logistic_regression.pkl")

# --- Random Forest ---
print("    Random Forest...", end=" ", flush=True)
rf = RandomForestClassifier(
    n_estimators=300, max_depth=10, min_samples_split=5,
    random_state=42, n_jobs=-1
)
rf.fit(X_train_res, y_train_res)
classical_results["random_forest"] = evaluate_sklearn(rf, X_val, y_val)
joblib.dump(rf, MODELS_DIR / "random_forest.pkl")
print(f"acc={classical_results['random_forest']['accuracy']:.4f}  → saved random_forest.pkl")

# --- Gradient Boosting ---
print("    Gradient Boosting...", end=" ", flush=True)
gbm = GradientBoostingClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.05,
    subsample=0.8, random_state=42
)
gbm.fit(X_train_res, y_train_res)
classical_results["gradient_boosting"] = evaluate_sklearn(gbm, X_val, y_val)
joblib.dump(gbm, MODELS_DIR / "gradient_boosting.pkl")
print(f"acc={classical_results['gradient_boosting']['accuracy']:.4f}  → saved gradient_boosting.pkl")

# --- XGBoost (uncalibrated — baseline before isotonic calibration) ---
print("    XGBoost (uncalibrated)...", end=" ", flush=True)
xgb = XGBClassifier(
    n_estimators=300, max_depth=8, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
    gamma=0.1, reg_alpha=0.1, reg_lambda=1.0,
    objective="binary:logistic", eval_metric="logloss",
    random_state=42, n_jobs=-1, verbosity=0,
)
xgb.fit(X_train_res, y_train_res)
classical_results["xgboost"] = evaluate_sklearn(xgb, X_val, y_val)
joblib.dump(xgb, MODELS_DIR / "xgboost_uncalibrated.pkl")
print(f"acc={classical_results['xgboost']['accuracy']:.4f}  → saved xgboost_uncalibrated.pkl")

model_performance = {
    "validation": classical_results,
    "test": {
        "final_model": "XGBoost + Isotonic (see train_model_no_phenotype.py)",
        "note": "Test metrics for the deployed model are in performance_no_phenotype.json",
    },
}
with open(MODELS_DIR / "model_performance.json", "w") as f:
    json.dump(model_performance, f, indent=2)
print(f"\n    Saved → models/model_performance.json")

# ---------------------------------------------------------------------------
# 5. Neural network architectures
# ---------------------------------------------------------------------------
print("\n[4] Preparing data for neural networks (StandardScaler)...")

scaler = StandardScaler()
X_tr_sc = scaler.fit_transform(X_train_res)
X_va_sc = scaler.transform(X_val)
X_te_sc = scaler.transform(X_test)
joblib.dump(scaler, MODELS_DIR / "nn_scaler.pkl")
print(f"    Scaler saved → models/nn_scaler.pkl")

N_FEATURES = X_train.shape[1]

def make_loader(X, y, batch_size=512, shuffle=True):
    Xt = torch.FloatTensor(X)
    yt = torch.FloatTensor(y)
    return DataLoader(TensorDataset(Xt, yt), batch_size=batch_size, shuffle=shuffle)

train_loader = make_loader(X_tr_sc, y_train_res)
val_loader   = make_loader(X_va_sc, y_val, shuffle=False)
test_loader  = make_loader(X_te_sc, y_test, shuffle=False)

# ---- Architecture definitions ----

class SimpleNN(nn.Module):
    def __init__(self, n_in):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 128), nn.ReLU(), nn.BatchNorm1d(128),
            nn.Linear(128, 64),  nn.ReLU(), nn.BatchNorm1d(64),
            nn.Linear(64, 1),    nn.Sigmoid(),
        )
    def forward(self, x):
        return self.net(x).squeeze(1)

class DeepNN_Dropout(nn.Module):
    def __init__(self, n_in):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(n_in, 256), nn.ReLU(), nn.BatchNorm1d(256), nn.Dropout(0.3),
            nn.Linear(256, 128),  nn.ReLU(), nn.BatchNorm1d(128), nn.Dropout(0.3),
            nn.Linear(128, 64),   nn.ReLU(), nn.BatchNorm1d(64),  nn.Dropout(0.2),
            nn.Linear(64, 32),    nn.ReLU(),
            nn.Linear(32, 1),     nn.Sigmoid(),
        )
    def forward(self, x):
        return self.net(x).squeeze(1)

class ResidualBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim), nn.ReLU(), nn.BatchNorm1d(dim),
            nn.Linear(dim, dim), nn.BatchNorm1d(dim),
        )
        self.relu = nn.ReLU()
    def forward(self, x):
        return self.relu(x + self.block(x))

class ResidualNN(nn.Module):
    def __init__(self, n_in):
        super().__init__()
        self.input_proj = nn.Linear(n_in, 128)
        self.res1 = ResidualBlock(128)
        self.res2 = ResidualBlock(128)
        self.head = nn.Sequential(nn.Linear(128, 64), nn.ReLU(),
                                  nn.Linear(64, 1), nn.Sigmoid())
    def forward(self, x):
        x = torch.relu(self.input_proj(x))
        x = self.res1(x)
        x = self.res2(x)
        return self.head(x).squeeze(1)

class AttentionNN(nn.Module):
    def __init__(self, n_in):
        super().__init__()
        self.attn = nn.Sequential(nn.Linear(n_in, n_in), nn.Softmax(dim=1))
        self.net  = nn.Sequential(
            nn.Linear(n_in, 128), nn.ReLU(), nn.BatchNorm1d(128),
            nn.Linear(128, 64),   nn.ReLU(),
            nn.Linear(64, 1),     nn.Sigmoid(),
        )
    def forward(self, x):
        return self.net(x * self.attn(x)).squeeze(1)

class WideDeepNN(nn.Module):
    def __init__(self, n_in):
        super().__init__()
        self.wide = nn.Linear(n_in, 64)
        self.deep = nn.Sequential(
            nn.Linear(n_in, 128), nn.ReLU(), nn.BatchNorm1d(128),
            nn.Linear(128, 64),   nn.ReLU(),
        )
        self.out = nn.Sequential(nn.Linear(128, 1), nn.Sigmoid())
    def forward(self, x):
        return self.out(torch.cat([self.wide(x), self.deep(x)], dim=1)).squeeze(1)

ARCHITECTURES = {
    "SimpleNN":      SimpleNN,
    "DeepNN_Dropout": DeepNN_Dropout,
    "ResidualNN":    ResidualNN,
    "AttentionNN":   AttentionNN,
    "WideDeepNN":    WideDeepNN,
}

# ---- Training loop ----

def train_nn(model, train_loader, val_loader, epochs=50, patience=8):
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)
    criterion = nn.BCELoss()
    best_val_loss, best_state, wait = float("inf"), None, 0

    for epoch in range(epochs):
        model.train()
        for Xb, yb in train_loader:
            Xb, yb = Xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            loss = criterion(model(Xb), yb)
            loss.backward()
            optimizer.step()

        model.eval()
        val_losses = []
        with torch.no_grad():
            for Xb, yb in val_loader:
                val_losses.append(criterion(model(Xb.to(DEVICE)), yb.to(DEVICE)).item())
        val_loss = np.mean(val_losses)
        scheduler.step(val_loss)

        if val_loss < best_val_loss:
            best_val_loss, best_state, wait = val_loss, {k: v.cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            wait += 1
            if wait >= patience:
                break

    model.load_state_dict(best_state)
    return model

def evaluate_nn(model, loader):
    model.eval()
    all_probs, all_labels = [], []
    with torch.no_grad():
        for Xb, yb in loader:
            probs = model(Xb.to(DEVICE)).cpu().numpy()
            all_probs.extend(probs)
            all_labels.extend(yb.numpy())
    probs  = np.array(all_probs)
    labels = np.array(all_labels)
    preds  = (probs >= 0.5).astype(int)
    return {
        "accuracy":  round(float(accuracy_score(labels, preds)),                    6),
        "precision": round(float(precision_score(labels, preds, zero_division=0)),  6),
        "recall":    round(float(recall_score(labels, preds)),                      6),
        "f1":        round(float(f1_score(labels, preds)),                          6),
        "auc_roc":   round(float(roc_auc_score(labels, probs)),                     6),
    }

# ---- Train all NN architectures ----
print("\n[5] Training neural network architectures (evaluated on TEST fold)...")

nn_results = {}
best_test_f1, best_name, best_model = 0.0, None, None

for name, Cls in ARCHITECTURES.items():
    print(f"\n    {name}...", flush=True)
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    model = Cls(N_FEATURES).to(DEVICE)
    model = train_nn(model, train_loader, val_loader)

    tr_m  = evaluate_nn(model, train_loader)
    va_m  = evaluate_nn(model, val_loader)
    te_m  = evaluate_nn(model, test_loader)
    gap   = round(tr_m["f1"] - va_m["f1"], 8)

    nn_results[name] = {
        "train":           tr_m,
        "validation":      va_m,
        "test":            te_m,
        "overfitting_gap": gap,
    }
    print(f"      Val  F1={va_m['f1']:.4f}  AUC={va_m['auc_roc']:.4f}")
    print(f"      Test F1={te_m['f1']:.4f}  AUC={te_m['auc_roc']:.4f}  gap={gap:.4f}")

    if te_m["f1"] > best_test_f1:
        best_test_f1, best_name = te_m["f1"], name
        best_model = {k: v.cpu().clone() for k, v in model.state_dict().items()}

# Save results
with open(MODELS_DIR / "neural_network_results.json", "w") as f:
    json.dump(nn_results, f, indent=2)

rows = [
    {
        "Model":       name,
        "Train_F1":    r["train"]["f1"],
        "Val_F1":      r["validation"]["f1"],
        "Test_F1":     r["test"]["f1"],
        "Test_AUC":    r["test"]["auc_roc"],
        "Overfit_Gap": r["overfitting_gap"],
    }
    for name, r in sorted(nn_results.items(), key=lambda x: -x[1]["test"]["f1"])
]
pd.DataFrame(rows).to_csv(MODELS_DIR / "nn_comparison.csv", index=False)

# Save best NN checkpoint
best_ckpt_path = MODELS_DIR / f"best_nn_{best_name}.pth"
torch.save(best_model, best_ckpt_path)
print(f"\n    Best NN: {best_name}  (Test F1={best_test_f1:.4f})")
print(f"    Saved → {best_ckpt_path}")
print(f"    Saved → models/neural_network_results.json")
print(f"    Saved → models/nn_comparison.csv")

# ---------------------------------------------------------------------------
# 6. Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("SUMMARY — Validation metrics (classical) / Test metrics (NNs)")
print("=" * 70)
print(f"{'Model':<28} {'Acc':>6} {'AUC':>7} {'F1':>7}")
print("-" * 52)
for name, m in classical_results.items():
    print(f"{name:<28} {m['accuracy']:>6.4f} {m['auc_roc']:>7.4f} {m['f1']:>7.4f}")
print()
for name, r in sorted(nn_results.items(), key=lambda x: -x[1]["test"]["f1"]):
    m = r["test"]
    print(f"{name:<28} {m['accuracy']:>6.4f} {m['auc_roc']:>7.4f} {m['f1']:>7.4f}")
print("=" * 70)
print("Done.")
