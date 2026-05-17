"""
Clean Training Data - Remove UTR Variants from Stop-Gained Classification
===========================================================================
This script filters out 3' UTR and 5' UTR variants that are incorrectly
classified as "stop-gained" or "nonsense" variants. These UTR variants
contaminate the training data and cause the model to incorrectly predict
benign for true protein-coding nonsense variants.

Problem:
- 18 benign KCNQ2 "stop" variants are 3' UTR variants (c.*xxx)
- These teach the model that "stop-gained in epilepsy gene = sometimes benign"
- True protein-coding nonsense (p.XxxTer) are 98.7% pathogenic

Solution:
- Filter out variants with c.*xxx (3' UTR) or c.-xxx (5' UTR) patterns
- Keep only true protein-coding variants
- Retrain model on cleaned data

Author: Data Cleaning Pipeline
Date: December 2025
"""

import pandas as pd
import numpy as np
from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).parent
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'

print("="*80)
print("CLEANING TRAINING DATA - REMOVING UTR VARIANTS")
print("="*80)

# ============================================
# LOAD DATA
# ============================================

print("\n1. Loading data...")

train = pd.read_csv(DATA_PROCESSED / 'train.csv')
val = pd.read_csv(DATA_PROCESSED / 'val.csv')
test = pd.read_csv(DATA_PROCESSED / 'test.csv')

print(f"   Train: {len(train):,} variants")
print(f"   Val:   {len(val):,} variants")
print(f"   Test:  {len(test):,} variants")

# ============================================
# IDENTIFY UTR VARIANTS
# ============================================

print("\n2. Identifying UTR variants...")

def is_utr_variant(name):
    """Check if variant is in UTR based on HGVS notation"""
    if pd.isna(name):
        return False

    name_str = str(name).lower()

    # 3' UTR: c.*xxx or c.*xxx+xxx
    utr_3_pattern = r'c\.\*\d+'

    # 5' UTR: c.-xxx or c.-xxx-xxx
    utr_5_pattern = r'c\.\-\d+'

    # Intronic: c.xxx+xxx or c.xxx-xxx (deep intronic)
    # We'll be more conservative here - only remove obvious UTR

    if re.search(utr_3_pattern, name_str):
        return True
    if re.search(utr_5_pattern, name_str):
        return True

    return False

# Mark UTR variants
train['is_utr'] = train['Name'].apply(is_utr_variant)
val['is_utr'] = val['Name'].apply(is_utr_variant)
test['is_utr'] = test['Name'].apply(is_utr_variant)

print(f"\n   UTR variants found:")
print(f"   Train: {train['is_utr'].sum():,} ({train['is_utr'].sum()/len(train)*100:.2f}%)")
print(f"   Val:   {val['is_utr'].sum():,} ({val['is_utr'].sum()/len(val)*100:.2f}%)")
print(f"   Test:  {test['is_utr'].sum():,} ({test['is_utr'].sum()/len(test)*100:.2f}%)")

# ============================================
# ANALYZE UTR VARIANTS BY LABEL
# ============================================

print("\n3. Analyzing UTR variants by label...")

for dataset_name, dataset in [('Train', train), ('Val', val), ('Test', test)]:
    utr_variants = dataset[dataset['is_utr']]
    if len(utr_variants) > 0:
        pathogenic = (utr_variants['Label'] == 1).sum()
        benign = (utr_variants['Label'] == 0).sum()
        print(f"\n   {dataset_name} UTR variants:")
        print(f"   - Pathogenic: {pathogenic} ({pathogenic/len(utr_variants)*100:.1f}%)")
        print(f"   - Benign: {benign} ({benign/len(utr_variants)*100:.1f}%)")

# Show some examples
print("\n4. Example UTR variants (train set):")
utr_examples = train[train['is_utr']][['GeneSymbol', 'Name', 'Label', 'ClinicalSignificance']].head(10)
for idx, row in utr_examples.iterrows():
    label_str = "PATHOGENIC" if row['Label'] == 1 else "BENIGN"
    print(f"   {row['GeneSymbol']:10s} | {row['Name'][:50]:50s} | {label_str}")

# ============================================
# FILTER OUT UTR VARIANTS
# ============================================

print("\n" + "="*80)
print("5. Filtering out UTR variants...")
print("="*80)

train_clean = train[~train['is_utr']].drop(columns=['is_utr']).reset_index(drop=True)
val_clean = val[~val['is_utr']].drop(columns=['is_utr']).reset_index(drop=True)
test_clean = test[~test['is_utr']].drop(columns=['is_utr']).reset_index(drop=True)

print(f"\nBefore filtering:")
print(f"   Train: {len(train):,} variants")
print(f"   Val:   {len(val):,} variants")
print(f"   Test:  {len(test):,} variants")

print(f"\nAfter filtering:")
print(f"   Train: {len(train_clean):,} variants (removed {len(train) - len(train_clean):,})")
print(f"   Val:   {len(val_clean):,} variants (removed {len(val) - len(val_clean):,})")
print(f"   Test:  {len(test_clean):,} variants (removed {len(test) - len(test_clean):,})")

# ============================================
# CHECK KCNQ2 STOP VARIANTS AFTER CLEANING
# ============================================

print("\n" + "="*80)
print("6. KCNQ2 Stop Variants After Cleaning")
print("="*80)

# Combined clean data
all_clean = pd.concat([train_clean, val_clean, test_clean], ignore_index=True)

kcnq2_clean = all_clean[all_clean['GeneSymbol'] == 'KCNQ2']
kcnq2_stop_clean = kcnq2_clean[
    kcnq2_clean['Name'].str.contains('stop|nonsense|ter|\\*', case=False, na=False, regex=True)
]

print(f"\nKCNQ2 stop variants after cleaning:")
print(f"   Total: {len(kcnq2_stop_clean)}")
print(f"   Pathogenic: {(kcnq2_stop_clean['Label']==1).sum()} ({(kcnq2_stop_clean['Label']==1).sum()/len(kcnq2_stop_clean)*100:.1f}%)")
print(f"   Benign: {(kcnq2_stop_clean['Label']==0).sum()} ({(kcnq2_stop_clean['Label']==0).sum()/len(kcnq2_stop_clean)*100:.1f}%)")

if (kcnq2_stop_clean['Label']==0).sum() > 0:
    print(f"\n   Remaining benign KCNQ2 stop variants:")
    benign_stop = kcnq2_stop_clean[kcnq2_stop_clean['Label']==0]
    for idx, row in benign_stop[['Name', 'ClinicalSignificance']].iterrows():
        print(f"   - {row['Name']}")

# ============================================
# SAVE CLEANED DATA
# ============================================

print("\n" + "="*80)
print("7. Saving cleaned data...")
print("="*80)

# Backup original files
import shutil
from datetime import datetime

backup_dir = DATA_PROCESSED / 'backup_before_utr_cleaning'
backup_dir.mkdir(exist_ok=True)

timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

print(f"\nBacking up original files to: {backup_dir}")
shutil.copy(DATA_PROCESSED / 'train.csv', backup_dir / f'train_{timestamp}.csv')
shutil.copy(DATA_PROCESSED / 'val.csv', backup_dir / f'val_{timestamp}.csv')
shutil.copy(DATA_PROCESSED / 'test.csv', backup_dir / f'test_{timestamp}.csv')

# Save cleaned data
train_clean.to_csv(DATA_PROCESSED / 'train.csv', index=False)
val_clean.to_csv(DATA_PROCESSED / 'val.csv', index=False)
test_clean.to_csv(DATA_PROCESSED / 'test.csv', index=False)

print(f"\n✅ Cleaned data saved:")
print(f"   {DATA_PROCESSED / 'train.csv'}")
print(f"   {DATA_PROCESSED / 'val.csv'}")
print(f"   {DATA_PROCESSED / 'test.csv'}")

# ============================================
# SUMMARY
# ============================================

print("\n" + "="*80)
print("✅ DATA CLEANING COMPLETE")
print("="*80)

print(f"\nSummary:")
print(f"   Removed {len(train) - len(train_clean):,} UTR variants from training")
print(f"   Removed {len(val) - len(val_clean):,} UTR variants from validation")
print(f"   Removed {len(test) - len(test_clean):,} UTR variants from test")
print(f"   Total removed: {(len(train) + len(val) + len(test)) - (len(train_clean) + len(val_clean) + len(test_clean)):,}")

print(f"\n   New dataset sizes:")
print(f"   Train: {len(train_clean):,} variants")
print(f"   Val:   {len(val_clean):,} variants")
print(f"   Test:  {len(test_clean):,} variants")

print("\n" + "="*80)
print("Next Steps:")
print("1. Run: python feature_engineering_no_phenotype.py")
print("2. Run: python train_model_no_phenotype.py")
print("3. Test: KCNQ2 stop-gained should now predict PATHOGENIC")
print("="*80)
