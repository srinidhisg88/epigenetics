"""
Check for Overfitting - Training vs Validation Analysis
=======================================================
This script loads the trained models and evaluates them on BOTH training
and validation sets to detect overfitting.

Overfitting indicators:
- Training accuracy >> Validation accuracy
- Training F1 >> Validation F1
- Large gap between training and validation metrics

Author: Overfitting Analysis
Date: 2024
"""

import pandas as pd
import numpy as np
import json
import joblib
from pathlib import Path
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix
)

# ============================================
# CONFIGURATION
# ============================================

PROJECT_ROOT = Path(__file__).parent
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'
MODELS_DIR = PROJECT_ROOT / 'models'

print("="*80)
print("OVERFITTING ANALYSIS: TRAINING vs VALIDATION vs TEST")
print("="*80)

# ============================================
# LOAD DATA
# ============================================

print("\n1. Loading data...")

X_train = pd.read_csv(DATA_PROCESSED / 'X_train.csv')
X_val = pd.read_csv(DATA_PROCESSED / 'X_val.csv')
X_test = pd.read_csv(DATA_PROCESSED / 'X_test.csv')

train_df = pd.read_csv(DATA_PROCESSED / 'train.csv')
val_df = pd.read_csv(DATA_PROCESSED / 'val.csv')
test_df = pd.read_csv(DATA_PROCESSED / 'test.csv')

y_train = train_df['Label']
y_val = val_df['Label']
y_test = test_df['Label']

print(f"   ✓ X_train: {X_train.shape}")
print(f"   ✓ X_val:   {X_val.shape}")
print(f"   ✓ X_test:  {X_test.shape}")

# ============================================
# LOAD TRAINED MODEL
# ============================================

print("\n2. Loading trained model...")

model_path = MODELS_DIR / 'epilepsy_classifier.pkl'
model = joblib.load(model_path)

print(f"   ✓ Model loaded: {model.__class__.__name__}")

# ============================================
# EVALUATION FUNCTION
# ============================================

def evaluate_model(model, X, y, dataset_name="Dataset"):
    """Evaluate model and return metrics"""

    # Predictions
    y_pred = model.predict(X)
    y_prob = model.predict_proba(X)[:, 1]

    # Metrics
    metrics = {
        'accuracy': accuracy_score(y, y_pred),
        'precision': precision_score(y, y_pred),
        'recall': recall_score(y, y_pred),
        'f1': f1_score(y, y_pred),
        'auc_roc': roc_auc_score(y, y_prob)
    }

    # Confusion matrix
    cm = confusion_matrix(y, y_pred)

    print(f"\n   {dataset_name}:")
    print(f"      Accuracy:  {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.2f}%)")
    print(f"      Precision: {metrics['precision']:.4f}")
    print(f"      Recall:    {metrics['recall']:.4f}")
    print(f"      F1 Score:  {metrics['f1']:.4f}")
    print(f"      AUC-ROC:   {metrics['auc_roc']:.4f}")

    print(f"\n      Confusion Matrix:")
    print(f"         TN: {cm[0,0]:>5}  FP: {cm[0,1]:>5}")
    print(f"         FN: {cm[1,0]:>5}  TP: {cm[1,1]:>5}")

    return metrics

# ============================================
# EVALUATE ON ALL DATASETS
# ============================================

print("\n" + "="*80)
print("EVALUATING MODEL ON ALL DATASETS")
print("="*80)

train_metrics = evaluate_model(model, X_train, y_train, "TRAINING SET")
val_metrics = evaluate_model(model, X_val, y_val, "VALIDATION SET")
test_metrics = evaluate_model(model, X_test, y_test, "TEST SET")

# ============================================
# OVERFITTING ANALYSIS
# ============================================

print("\n" + "="*80)
print("OVERFITTING ANALYSIS")
print("="*80)

# Calculate gaps
accuracy_gap_train_val = train_metrics['accuracy'] - val_metrics['accuracy']
accuracy_gap_val_test = val_metrics['accuracy'] - test_metrics['accuracy']
f1_gap_train_val = train_metrics['f1'] - val_metrics['f1']
f1_gap_val_test = val_metrics['f1'] - test_metrics['f1']
auc_gap_train_val = train_metrics['auc_roc'] - val_metrics['auc_roc']
auc_gap_val_test = val_metrics['auc_roc'] - test_metrics['auc_roc']

print("\n1. METRIC GAPS (Train - Validation):")
print(f"   Accuracy Gap:  {accuracy_gap_train_val:+.4f} ({accuracy_gap_train_val*100:+.2f}%)")
print(f"   F1 Gap:        {f1_gap_train_val:+.4f} ({f1_gap_train_val*100:+.2f}%)")
print(f"   AUC-ROC Gap:   {auc_gap_train_val:+.4f} ({auc_gap_train_val*100:+.2f}%)")

print("\n2. METRIC GAPS (Validation - Test):")
print(f"   Accuracy Gap:  {accuracy_gap_val_test:+.4f} ({accuracy_gap_val_test*100:+.2f}%)")
print(f"   F1 Gap:        {f1_gap_val_test:+.4f} ({f1_gap_val_test*100:+.2f}%)")
print(f"   AUC-ROC Gap:   {auc_gap_val_test:+.4f} ({auc_gap_val_test*100:+.2f}%)")

# ============================================
# OVERFITTING VERDICT
# ============================================

print("\n" + "="*80)
print("OVERFITTING VERDICT")
print("="*80)

# Define thresholds for overfitting detection
SEVERE_OVERFITTING_THRESHOLD = 0.10  # 10% gap
MODERATE_OVERFITTING_THRESHOLD = 0.05  # 5% gap
MINOR_OVERFITTING_THRESHOLD = 0.02  # 2% gap

def diagnose_overfitting(train_metric, val_metric, metric_name):
    """Diagnose overfitting based on metric gap"""
    gap = train_metric - val_metric
    gap_pct = gap * 100

    print(f"\n{metric_name}:")
    print(f"   Train:      {train_metric:.4f}")
    print(f"   Validation: {val_metric:.4f}")
    print(f"   Gap:        {gap:+.4f} ({gap_pct:+.2f}%)")

    if gap > SEVERE_OVERFITTING_THRESHOLD:
        print(f"   ⚠️  SEVERE OVERFITTING DETECTED!")
        return "SEVERE"
    elif gap > MODERATE_OVERFITTING_THRESHOLD:
        print(f"   ⚠️  MODERATE OVERFITTING")
        return "MODERATE"
    elif gap > MINOR_OVERFITTING_THRESHOLD:
        print(f"   ⚡ MINOR OVERFITTING (acceptable)")
        return "MINOR"
    elif gap > -MINOR_OVERFITTING_THRESHOLD:
        print(f"   ✅ WELL GENERALIZED")
        return "GOOD"
    else:
        print(f"   🤔 VALIDATION BETTER THAN TRAINING (unusual, possible underfitting)")
        return "UNUSUAL"

print("\nAnalyzing each metric:")
print("-" * 80)

accuracy_status = diagnose_overfitting(train_metrics['accuracy'], val_metrics['accuracy'], "ACCURACY")
f1_status = diagnose_overfitting(train_metrics['f1'], val_metrics['f1'], "F1 SCORE")
auc_status = diagnose_overfitting(train_metrics['auc_roc'], val_metrics['auc_roc'], "AUC-ROC")

# Overall verdict
print("\n" + "="*80)
print("FINAL VERDICT")
print("="*80)

overfitting_scores = {
    "SEVERE": 3,
    "MODERATE": 2,
    "MINOR": 1,
    "GOOD": 0,
    "UNUSUAL": 0
}

total_score = (overfitting_scores[accuracy_status] +
               overfitting_scores[f1_status] +
               overfitting_scores[auc_status])

if total_score >= 6:
    verdict = "🚨 SEVERE OVERFITTING"
    explanation = "The model has memorized the training data and will not generalize well."
    recommendation = "CRITICAL: Reduce model complexity, add regularization, or get more data."
elif total_score >= 3:
    verdict = "⚠️  MODERATE OVERFITTING"
    explanation = "The model shows signs of overfitting but may still be usable."
    recommendation = "Consider: Increase regularization, reduce model complexity, or cross-validation."
elif total_score >= 1:
    verdict = "⚡ MINOR OVERFITTING (Acceptable)"
    explanation = "Small gap is normal and acceptable for complex models."
    recommendation = "Model is acceptable. Monitor performance on new data."
else:
    verdict = "✅ WELL GENERALIZED MODEL"
    explanation = "The model generalizes well from training to validation."
    recommendation = "Model is ready for deployment. Great job!"

print(f"\n{verdict}")
print(f"\n{explanation}")
print(f"\nRecommendation: {recommendation}")

# ============================================
# COMPARATIVE SUMMARY TABLE
# ============================================

print("\n" + "="*80)
print("COMPARATIVE SUMMARY TABLE")
print("="*80)

summary = pd.DataFrame({
    'Dataset': ['Training', 'Validation', 'Test'],
    'Samples': [len(X_train), len(X_val), len(X_test)],
    'Accuracy': [train_metrics['accuracy'], val_metrics['accuracy'], test_metrics['accuracy']],
    'Precision': [train_metrics['precision'], val_metrics['precision'], test_metrics['precision']],
    'Recall': [train_metrics['recall'], val_metrics['recall'], test_metrics['recall']],
    'F1': [train_metrics['f1'], val_metrics['f1'], test_metrics['f1']],
    'AUC-ROC': [train_metrics['auc_roc'], val_metrics['auc_roc'], test_metrics['auc_roc']]
})

print("\n")
print(summary.to_string(index=False))

# ============================================
# SAVE RESULTS
# ============================================

print("\n" + "="*80)
print("SAVING RESULTS")
print("="*80)

results = {
    'training_metrics': {k: float(v) for k, v in train_metrics.items()},
    'validation_metrics': {k: float(v) for k, v in val_metrics.items()},
    'test_metrics': {k: float(v) for k, v in test_metrics.items()},
    'overfitting_analysis': {
        'train_val_gaps': {
            'accuracy': float(accuracy_gap_train_val),
            'f1': float(f1_gap_train_val),
            'auc_roc': float(auc_gap_train_val)
        },
        'val_test_gaps': {
            'accuracy': float(accuracy_gap_val_test),
            'f1': float(f1_gap_val_test),
            'auc_roc': float(auc_gap_val_test)
        },
        'status': {
            'accuracy': accuracy_status,
            'f1': f1_status,
            'auc_roc': auc_status
        },
        'verdict': verdict,
        'explanation': explanation,
        'recommendation': recommendation
    }
}

output_path = MODELS_DIR / 'overfitting_analysis.json'
with open(output_path, 'w') as f:
    json.dump(results, f, indent=2)

print(f"\n✅ Results saved: {output_path}")

# Save summary table as CSV
summary_path = MODELS_DIR / 'performance_comparison.csv'
summary.to_csv(summary_path, index=False)
print(f"✅ Summary table saved: {summary_path}")

print("\n" + "="*80)
print("ANALYSIS COMPLETE!")
print("="*80)
