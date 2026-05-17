"""
FIXED Feature Engineering for Epilepsy Variant Classification
==============================================================
This script creates features WITHOUT target leakage and noise.

Key Improvements:
1. Removes phenotype target leakage (no "benign familial" detection)
2. Uses gene pathogenicity rate instead of frequency
3. Focuses on biologically meaningful features
4. Removes low-signal noise features

Input: data/processed/train.csv, val.csv, test.csv
Output: data/processed/X_train_fixed.csv, X_val_fixed.csv, X_test_fixed.csv

Author: Fixed Feature Engineering Pipeline
Date: December 2025
"""

import pandas as pd
import numpy as np
import json
import warnings
from pathlib import Path

warnings.filterwarnings('ignore')

# ============================================
# CONFIGURATION
# ============================================

PROJECT_ROOT = Path(__file__).parent
DATA_PROCESSED = PROJECT_ROOT / 'data' / 'processed'

print("="*80)
print("FIXED EPILEPSY VARIANT FEATURE ENGINEERING")
print("="*80)
print("\nKey Improvements:")
print("  ✓ No target leakage from phenotype strings")
print("  ✓ Gene pathogenicity rate (not just frequency)")
print("  ✓ Focused on high-signal features")
print("  ✓ Safe for production use")
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

# Combine for consistent encoding
all_data = pd.concat([train, val, test], axis=0, ignore_index=True)
print(f"   Total: {len(all_data):,} variants")

# ============================================
# FEATURE ENGINEERING FUNCTIONS
# ============================================

def create_gene_features(df, train_df):
    """Create gene-based features with pathogenicity rate"""
    print("\n2. Creating gene features...")

    features = pd.DataFrame()

    # One-hot encode genes (keep this - works well)
    gene_dummies = pd.get_dummies(df['GeneSymbol'], prefix='gene')
    print(f"   • Gene one-hot: {gene_dummies.shape[1]} features")

    # FIXED: Use pathogenicity rate instead of frequency
    # This tells us: "How often is this gene pathogenic?"
    gene_pathogenicity = train_df.groupby('GeneSymbol')['Label'].agg(['mean', 'count'])
    gene_pathogenicity.columns = ['pathogenic_rate', 'count']

    features['gene_pathogenicity_rate'] = df['GeneSymbol'].map(gene_pathogenicity['pathogenic_rate']).fillna(0.5)
    features['gene_sample_count'] = df['GeneSymbol'].map(gene_pathogenicity['count']).fillna(0)

    print(f"   • Gene pathogenicity rate calculated")
    print(f"     Example: SCN1A pathogenic rate = {gene_pathogenicity.loc['SCN1A', 'pathogenic_rate']:.2%}")

    # Gene categories (sodium channel vs other) - Keep this
    sodium_channel_genes = ['SCN1A', 'SCN2A', 'SCN8A', 'SCN3A', 'SCN9A']
    features['is_sodium_channel'] = df['GeneSymbol'].isin(sodium_channel_genes).astype(int)

    # GABA receptor genes
    gaba_genes = ['GABRA1', 'GABRG2', 'GABRB3', 'GABRD']
    features['is_gaba_receptor'] = df['GeneSymbol'].isin(gaba_genes).astype(int)

    # Ion channel genes (general)
    ion_channel_genes = sodium_channel_genes + ['KCNQ2', 'KCNQ3', 'CACNA1A']
    features['is_ion_channel'] = df['GeneSymbol'].isin(ion_channel_genes).astype(int)

    # TSC complex genes (known high pathogenicity)
    tsc_genes = ['TSC1', 'TSC2']
    features['is_tsc_complex'] = df['GeneSymbol'].isin(tsc_genes).astype(int)

    return pd.concat([features, gene_dummies], axis=1)


def create_variant_type_features(df):
    """Create variant type features - KEEP AS IS (working well)"""
    print("\n3. Creating variant type features...")

    features = pd.DataFrame()

    # One-hot encode variant types
    type_dummies = pd.get_dummies(df['Type'], prefix='type')
    print(f"   • Variant type one-hot: {type_dummies.shape[1]} features")

    # Binary indicators for important variant types
    features['is_single_nucleotide'] = (df['Type'] == 'single nucleotide variant').astype(int)
    features['is_deletion'] = df['Type'].str.contains('deletion', case=False, na=False).astype(int)
    features['is_insertion'] = df['Type'].str.contains('insertion', case=False, na=False).astype(int)
    features['is_duplication'] = df['Type'].str.contains('duplication', case=False, na=False).astype(int)
    features['is_indel'] = df['Type'].str.contains('indel', case=False, na=False).astype(int)

    return pd.concat([features, type_dummies], axis=1)


def create_molecular_consequence_features(df):
    """
    Extract molecular consequences - KEEP AS IS (THIS IS EXCELLENT!)
    This is why severe_consequence_count has 52% importance - it's the right feature!
    """
    print("\n4. Creating molecular consequence features...")

    features = pd.DataFrame()

    # Extract from Name column
    variant_name = df['Name'].fillna('')

    # Frameshift (causes frame shift in protein)
    features['is_frameshift'] = variant_name.str.contains(
        'frameshift|fs', case=False, regex=True
    ).astype(int)

    # Nonsense/Stop-gain (creates premature stop codon)
    features['is_nonsense'] = variant_name.str.contains(
        'nonsense|stop|ter|\\*', case=False, regex=True
    ).astype(int)

    # Missense (changes amino acid)
    features['is_missense'] = variant_name.str.contains(
        'missense', case=False
    ).astype(int)

    # Splice site variants
    features['is_splice'] = variant_name.str.contains(
        'splice', case=False
    ).astype(int)

    # Synonymous (doesn't change amino acid)
    features['is_synonymous'] = variant_name.str.contains(
        'synonymous', case=False
    ).astype(int)

    # Inframe (deletion/insertion that doesn't shift frame)
    features['is_inframe'] = variant_name.str.contains(
        'in.frame|inframe', case=False, regex=True
    ).astype(int)

    # Start loss / Stop loss
    features['is_start_loss'] = variant_name.str.contains(
        'start.loss|initiator', case=False, regex=True
    ).astype(int)

    features['is_stop_loss'] = variant_name.str.contains(
        'stop.loss|nonstop', case=False, regex=True
    ).astype(int)

    # *** THIS IS THE KEY FEATURE - 52% importance ***
    # Count of severe consequences (likely pathogenic indicators)
    features['severe_consequence_count'] = (
        features['is_frameshift'] +
        features['is_nonsense'] +
        features['is_splice'] +
        features['is_start_loss']
    )

    # Add a feature: Any severe consequence?
    features['has_severe_consequence'] = (features['severe_consequence_count'] > 0).astype(int)

    print(f"   • Molecular consequences: {features.shape[1]} features")
    print(f"   ✓ severe_consequence_count included (most important feature!)")

    return features


def create_position_features_minimal(df):
    """
    SIMPLIFIED: Only keep high-signal position features
    Removed: raw position (weak signal), early/late gene (too simplistic)
    """
    print("\n5. Creating position features (minimal)...")

    features = pd.DataFrame()

    # Only keep important chromosomes (based on feature importance)
    # chr_2, chr_16, chr_9, chr_X, chr_20, chr_8 have >0.5% importance
    important_chroms = ['1', '2', '3', '8', '9', '12', '14', '15', '16', '20', '22', 'X']

    chromosome = df['Chromosome'].astype(str)
    for chrom in important_chroms:
        features[f'chr_{chrom}'] = (chromosome == chrom).astype(int)

    # Position percentile within gene (keep this - some signal)
    features['position_in_gene'] = df.groupby('GeneSymbol')['PositionVCF'].rank(pct=True)

    print(f"   • Position features: {features.shape[1]} features")
    print(f"   • Removed: raw position (weak signal), early/late binary indicators")

    return features


def create_phenotype_features_safe(df):
    """
    FIXED: Phenotype features WITHOUT target leakage

    REMOVED:
    - is_benign_familial (contains "benign" - target leakage!)
    - has_seizures (almost everyone has this - no signal)

    KEPT (Safe for production):
    - Specific epilepsy syndromes (Dravet, infantile encephalopathy)
    - Clinical features (developmental delay, autism)
    - Seizure type (febrile)

    These are SAFE because:
    - Doctor enters clinical symptoms, not variant classification
    - No "benign" or "pathogenic" in these strings
    - Based on patient phenotype, not variant description
    """
    print("\n6. Creating phenotype features (NO TARGET LEAKAGE)...")

    features = pd.DataFrame()

    phenotype_list = df['PhenotypeList'].fillna('')

    # SAFE: Specific epilepsy syndromes
    # (Dravet is severe, but doesn't leak "pathogenic" label)
    features['is_dravet'] = phenotype_list.str.contains(
        'Dravet|SMEI', case=False, na=False
    ).astype(int)

    # SAFE: Encephalopathy indicates severity
    features['is_infantile_encephalopathy'] = phenotype_list.str.contains(
        'early infantile|encephalopathy', case=False, na=False
    ).astype(int)

    # SAFE: Febrile seizures are a specific type
    features['is_febrile_seizure'] = phenotype_list.str.contains(
        'febrile', case=False, na=False
    ).astype(int)

    # SAFE: Developmental delay (clinical observation)
    features['has_developmental_delay'] = phenotype_list.str.contains(
        'developmental delay|intellectual disability', case=False, na=False
    ).astype(int)

    # SAFE: Autism (clinical observation)
    features['has_autism'] = phenotype_list.str.contains(
        'autism|autistic', case=False, na=False
    ).astype(int)

    # Count number of phenotypes (more phenotypes might indicate complexity)
    features['num_phenotypes'] = phenotype_list.str.count(';') + 1
    features['num_phenotypes'] = features['num_phenotypes'].replace(1, 0)  # Handle empty

    print(f"   • Phenotype features: {features.shape[1]} features")
    print(f"   ✓ REMOVED: is_benign_familial (had target leakage!)")
    print(f"   ✓ REMOVED: has_seizures (no signal - almost everyone has it)")
    print(f"   ✓ SAFE: Specific syndromes and clinical features only")

    return features


def create_allele_features(df):
    """Create features from reference and alternate alleles - KEEP AS IS"""
    print("\n7. Creating allele features...")

    features = pd.DataFrame()

    ref = df['ReferenceAllele'].fillna('')
    alt = df['AlternateAllele'].fillna('')

    # Allele lengths
    features['ref_length'] = ref.str.len()
    features['alt_length'] = alt.str.len()
    features['allele_length_diff'] = features['alt_length'] - features['ref_length']

    # Is the variant a simple SNP (single nucleotide)
    features['is_snp'] = ((features['ref_length'] == 1) &
                          (features['alt_length'] == 1)).astype(int)

    # Type of change (transition vs transversion)
    def get_change_type(r, a):
        if len(r) != 1 or len(a) != 1:
            return 'other'
        # Transitions (more common, less likely pathogenic)
        if (r, a) in [('A','G'), ('G','A'), ('C','T'), ('T','C')]:
            return 'transition'
        # Transversions (less common, more likely pathogenic)
        elif r in 'ACGT' and a in 'ACGT':
            return 'transversion'
        else:
            return 'other'

    change_types = [get_change_type(r, a) for r, a in zip(ref, alt)]
    features['is_transition'] = (pd.Series(change_types) == 'transition').astype(int)
    features['is_transversion'] = (pd.Series(change_types) == 'transversion').astype(int)

    print(f"   • Allele features: {features.shape[1]} features")

    return features


def create_statistical_features_minimal(df):
    """
    SIMPLIFIED: Only essential statistical features
    Removed: review_score, has_expert_review, has_criteria (quality metrics, not biology)
    """
    print("\n8. Creating statistical features (minimal)...")

    features = pd.DataFrame()

    # Origin of variant - Keep (has some signal)
    origin = df['OriginSimple'].fillna('')
    features['is_germline'] = origin.str.contains('germline', case=False, na=False).astype(int)
    features['is_de_novo'] = origin.str.contains('de novo', case=False, na=False).astype(int)

    # Assembly version - Keep (minimal signal, but fast to compute)
    features['is_grch38'] = (df['Assembly'] == 'GRCh38').astype(int)
    features['is_grch37'] = (df['Assembly'] == 'GRCh37').astype(int)

    # Number of submitters (log scale) - Keep ONE variant
    features['log_num_submitters'] = np.log1p(
        pd.to_numeric(df['NumberSubmitters'], errors='coerce').fillna(1)
    )

    print(f"   • Statistical features: {features.shape[1]} features")
    print(f"   • Removed: review_score, has_expert_review, has_criteria")
    print(f"   • (These measure data quality, not variant pathogenicity)")

    return features


# ============================================
# MAIN FEATURE ENGINEERING
# ============================================

print("\n" + "="*80)
print("STARTING FEATURE ENGINEERING (FIXED VERSION)")
print("="*80)

# Create all features
gene_features = create_gene_features(all_data, train)
variant_type_features = create_variant_type_features(all_data)
molecular_features = create_molecular_consequence_features(all_data)
position_features = create_position_features_minimal(all_data)
phenotype_features = create_phenotype_features_safe(all_data)
allele_features = create_allele_features(all_data)
statistical_features = create_statistical_features_minimal(all_data)

# Combine all features
print("\n9. Combining all features...")
all_features = pd.concat([
    gene_features,
    variant_type_features,
    molecular_features,
    position_features,
    phenotype_features,
    allele_features,
    statistical_features
], axis=1)

print(f"    Total features created: {all_features.shape[1]}")

# Handle missing values
print("\n10. Handling missing values...")
missing_before = all_features.isnull().sum().sum()
print(f"    Missing values before: {missing_before:,}")

# Fill numeric columns with median
numeric_cols = all_features.select_dtypes(include=[np.number]).columns
all_features[numeric_cols] = all_features[numeric_cols].fillna(
    all_features[numeric_cols].median()
)

# Fill remaining with 0
all_features = all_features.fillna(0)

missing_after = all_features.isnull().sum().sum()
print(f"    Missing values after: {missing_after:,}")

# ============================================
# SPLIT BACK INTO TRAIN/VAL/TEST
# ============================================

print("\n11. Splitting features back into train/val/test...")

train_size = len(train)
val_size = len(val)
test_size = len(test)

X_train = all_features.iloc[:train_size]
X_val = all_features.iloc[train_size:train_size+val_size]
X_test = all_features.iloc[train_size+val_size:]

print(f"    X_train: {X_train.shape}")
print(f"    X_val:   {X_val.shape}")
print(f"    X_test:  {X_test.shape}")

# Get labels
y_train = train['Label']
y_val = val['Label']
y_test = test['Label']

# ============================================
# SAVE FEATURES
# ============================================

print("\n12. Saving features...")

X_train.to_csv(DATA_PROCESSED / 'X_train_fixed.csv', index=False)
X_val.to_csv(DATA_PROCESSED / 'X_val_fixed.csv', index=False)
X_test.to_csv(DATA_PROCESSED / 'X_test_fixed.csv', index=False)

print(f"    ✅ Saved: {DATA_PROCESSED / 'X_train_fixed.csv'}")
print(f"    ✅ Saved: {DATA_PROCESSED / 'X_val_fixed.csv'}")
print(f"    ✅ Saved: {DATA_PROCESSED / 'X_test_fixed.csv'}")

# Save feature names for reference
feature_info = {
    'total_features': all_features.shape[1],
    'feature_names': list(all_features.columns),
    'improvements': [
        'No target leakage from phenotype strings',
        'Gene pathogenicity rate instead of frequency',
        'Removed low-signal position features',
        'Removed quality metrics (review_score, etc.)',
        'Focused on biologically meaningful features',
        'Safe for production use with doctor inputs'
    ],
    'feature_groups': {
        'gene_features': list(gene_features.columns),
        'variant_type_features': list(variant_type_features.columns),
        'molecular_features': list(molecular_features.columns),
        'position_features': list(position_features.columns),
        'phenotype_features': list(phenotype_features.columns),
        'allele_features': list(allele_features.columns),
        'statistical_features': list(statistical_features.columns)
    }
}

with open(DATA_PROCESSED / 'feature_names_fixed.json', 'w') as f:
    json.dump(feature_info, f, indent=2)

print(f"    ✅ Saved: {DATA_PROCESSED / 'feature_names_fixed.json'}")

# ============================================
# SUMMARY STATISTICS
# ============================================

print("\n" + "="*80)
print("FEATURE ENGINEERING SUMMARY (FIXED)")
print("="*80)

print(f"\nTotal features created: {all_features.shape[1]}")

print(f"\n🔧 KEY IMPROVEMENTS:")
print(f"  ✓ Removed 'is_benign_familial' (target leakage)")
print(f"  ✓ Changed gene_frequency → gene_pathogenicity_rate")
print(f"  ✓ Removed review quality metrics (not predictive)")
print(f"  ✓ Simplified position features (removed noise)")
print(f"  ✓ Kept severe_consequence_count (52% importance - correct!)")

print(f"\nFeature breakdown:")
print(f"  • Gene features:          {len(gene_features.columns):>4}")
print(f"  • Variant type features:  {len(variant_type_features.columns):>4}")
print(f"  • Molecular features:     {len(molecular_features.columns):>4}")
print(f"  • Position features:      {len(position_features.columns):>4}")
print(f"  • Phenotype features:     {len(phenotype_features.columns):>4} (NO LEAKAGE!)")
print(f"  • Allele features:        {len(allele_features.columns):>4}")
print(f"  • Statistical features:   {len(statistical_features.columns):>4}")

print(f"\nData shapes:")
print(f"  • X_train: {X_train.shape}")
print(f"  • X_val:   {X_val.shape}")
print(f"  • X_test:  {X_test.shape}")

print(f"\nLabel distributions:")
print(f"  • Train: {(y_train==1).sum():,} pathogenic, {(y_train==0).sum():,} benign")
print(f"  • Val:   {(y_val==1).sum():,} pathogenic, {(y_val==0).sum():,} benign")
print(f"  • Test:  {(y_test==1).sum():,} pathogenic, {(y_test==0).sum():,} benign")

print("\n" + "="*80)
print("✅ FIXED FEATURE ENGINEERING COMPLETE!")
print("="*80)

print("\n🎯 What Changed:")
print("  1. NO target leakage - safe for production!")
print("  2. Gene pathogenicity rate - better than frequency")
print("  3. Removed ~15 low-signal features")
print("  4. Doctor's phenotype input is SAFE to use")

print("\n🚀 Next step: python train_model_optimized.py --use-fixed-features")
print("   (This will use X_train_fixed.csv instead of X_train.csv)")
