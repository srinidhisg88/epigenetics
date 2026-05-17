import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split

# ============================================
# PART 1: LOAD AND PROCESS OMIM DATA
# ============================================

print("Loading OMIM gene-disease mappings...")
omim = pd.read_csv('data/raw/mim2gene.txt', 
                   sep='\t', 
                   comment='#',  # Skip comment lines
                   names=['MIM_Number', 'MIM_Entry_Type', 'Entrez_Gene_ID', 
                          'Gene_Symbol', 'Ensembl_Gene_ID'])

# Filter for genes only (not phenotypes)
omim_genes = omim[omim['MIM_Entry_Type'] == 'gene'].copy()

print(f"Total OMIM genes: {len(omim_genes):,}")
print(f"Sample OMIM data:")
print(omim_genes.head())

# ============================================
# PART 2: DEFINE EPILEPSY GENES
# ============================================

EPILEPSY_GENES = [
    'SCN1A', 'SCN2A', 'SCN8A', 'SCN3A', 'SCN9A',  # Sodium channels
    'CDKL5', 'STXBP1', 'KCNQ2', 'KCNQ3',          # Ion channels
    'PCDH19', 'CHD2', 'GABRA1', 'GABRG2',          # GABA receptors
    'SLC2A1', 'DEPDC5', 'NPRL3', 'TSC1', 'TSC2',   # mTOR pathway
    'MECP2', 'FOXG1', 'ARX', 'SLC6A1',             # Neurodevelopmental
    'ALDH7A1', 'PLCB1', 'PRRT2', 'TBC1D24'         # Metabolic/other
]

# Epilepsy-related phenotypes (HPO codes)
EPILEPSY_PHENOTYPES = [
    'HP:0001250',  # Seizures (general)
    'HP:0002069',  # Generalized tonic-clonic seizures
    'HP:0002121',  # Absence seizures
    'HP:0007359',  # Focal-onset seizure
    'HP:0011147',  # Typical absence seizures
    'HP:0010818',  # Generalized tonic seizures
    'HP:0002373',  # Febrile seizures
    'HP:0001249',  # Intellectual disability (common comorbidity)
    'HP:0001263',  # Developmental delay (common comorbidity)
]

# ============================================
# PART 3: LOAD AND FILTER CLINVAR
# ============================================
try:
    print("\nLoading ClinVar data...")
    clinvar = pd.read_csv('data/raw/variant_summary.txt', 
                        sep='\t', 
                        low_memory=False)

    print(f"Total ClinVar variants: {len(clinvar):,}")
except Exception as e:
    print(e)

# Filter for epilepsy genes
print("\nFiltering for epilepsy genes...")
epilepsy_data = clinvar[clinvar['GeneSymbol'].isin(EPILEPSY_GENES)].copy()

print(f"Epilepsy-related variants: {len(epilepsy_data):,}")
print(f"\n📊 Variants per gene:")
gene_counts = epilepsy_data['GeneSymbol'].value_counts()
print(gene_counts)

# ============================================
# PART 4: MERGE WITH OMIM DATA
# ============================================

print("\nMerging ClinVar with OMIM data...")

# Merge to get MIM numbers for genes
epilepsy_data = epilepsy_data.merge(
    omim_genes[['Gene_Symbol', 'MIM_Number']], 
    left_on='GeneSymbol', 
    right_on='Gene_Symbol', 
    how='left'
)

# Count how many have OMIM entries
has_omim = epilepsy_data['MIM_Number'].notna().sum()
print(f"✅ Variants with OMIM gene IDs: {has_omim:,} ({has_omim/len(epilepsy_data)*100:.1f}%)")

# ============================================
# PART 5: QUALITY FILTERING
# ============================================

print("\nApplying quality filters...")

quality_filter = (
    # Has clinical significance
    (epilepsy_data['ClinicalSignificance'].notna()) &
    # Has review status
    (epilepsy_data['ReviewStatus'].notna()) &
    # Has disease/phenotype information
    (epilepsy_data['PhenotypeList'].notna()) &
    # Germline (inherited, not cancer/somatic)
    (epilepsy_data['OriginSimple'].str.contains('germline', case=False, na=False))
)

epilepsy_filtered = epilepsy_data[quality_filter].copy()

print(f"High-quality epilepsy variants: {len(epilepsy_filtered):,}")
print(f"Filtered out: {len(epilepsy_data) - len(epilepsy_filtered):,} low-quality variants")

# ============================================
# PART 6: ANALYZE DATA DISTRIBUTIONS
# ============================================

print("\n" + "="*60)
print("DATA ANALYSIS")
print("="*60)

# Clinical Significance distribution
print("\n📊 Clinical Significance Distribution:")
sig_counts = epilepsy_filtered['ClinicalSignificance'].value_counts()
print(sig_counts)
print(f"\nTotal: {len(epilepsy_filtered):,}")

# Review Status distribution
print("\n⭐ Review Status Distribution:")
review_counts = epilepsy_filtered['ReviewStatus'].value_counts()
print(review_counts.head(10))

# Top epilepsy syndromes
print("\n🧬 Top 15 Epilepsy Syndromes/Phenotypes:")
phenotype_counts = epilepsy_filtered['PhenotypeList'].value_counts()
print(phenotype_counts.head(15))

# Variant types
print("\n🔬 Variant Type Distribution:")
type_counts = epilepsy_filtered['Type'].value_counts()
print(type_counts.head(10))

# ============================================
# PART 7: CREATE ML DATASET
# ============================================

print("\n" + "="*60)
print("CREATING ML TRAINING DATASET")
print("="*60)

# Filter for clear labels (Pathogenic or Benign)
labeled_data = epilepsy_filtered[
    epilepsy_filtered['ClinicalSignificance'].isin([
        'Pathogenic', 
        'Likely pathogenic',
        'Benign', 
        'Likely benign'
    ])
].copy()

# Create binary label
# 1 = Pathogenic (disease-causing)
# 0 = Benign (harmless)
labeled_data['Label'] = labeled_data['ClinicalSignificance'].apply(
    lambda x: 1 if 'pathogenic' in x.lower() and 'benign' not in x.lower() else 0
)

print(f"\n📚 Total labeled variants: {len(labeled_data):,}")
print(f"   ✅ Pathogenic/Likely pathogenic: {(labeled_data['Label']==1).sum():,}")
print(f"   ❌ Benign/Likely benign: {(labeled_data['Label']==0).sum():,}")

# Check class balance
pathogenic_pct = (labeled_data['Label']==1).sum() / len(labeled_data) * 100
print(f"\n⚖️  Class balance: {pathogenic_pct:.1f}% pathogenic, {100-pathogenic_pct:.1f}% benign")

if pathogenic_pct < 30 or pathogenic_pct > 70:
    print("⚠️  Warning: Classes are imbalanced. Will need to handle this in training.")

# ============================================
# PART 8: TRAIN/VAL/TEST SPLIT
# ============================================

print("\nCreating train/validation/test splits...")

# Split: 70% train, 15% val, 15% test
train_data, temp_data = train_test_split(
    labeled_data, 
    test_size=0.3, 
    random_state=42, 
    stratify=labeled_data['Label']
)

val_data, test_data = train_test_split(
    temp_data, 
    test_size=0.5, 
    random_state=42, 
    stratify=temp_data['Label']
)

print(f"\n📂 Data splits:")
print(f"   Train: {len(train_data):,} variants ({len(train_data)/len(labeled_data)*100:.1f}%)")
print(f"   Val:   {len(val_data):,} variants ({len(val_data)/len(labeled_data)*100:.1f}%)")
print(f"   Test:  {len(test_data):,} variants ({len(test_data)/len(labeled_data)*100:.1f}%)")

# Verify stratification
print(f"\n✓ Train set: {(train_data['Label']==1).sum()/len(train_data)*100:.1f}% pathogenic")
print(f"✓ Val set:   {(val_data['Label']==1).sum()/len(val_data)*100:.1f}% pathogenic")
print(f"✓ Test set:  {(test_data['Label']==1).sum()/len(test_data)*100:.1f}% pathogenic")

# ============================================
# PART 9: SAVE PROCESSED DATA
# ============================================

print("\nSaving processed datasets...")

# Save all filtered data (for reference)
epilepsy_filtered.to_csv('data/processed/epilepsy_variants_all.csv', index=False)

# Save train/val/test splits
train_data.to_csv('data/processed/train.csv', index=False)
val_data.to_csv('data/processed/val.csv', index=False)
test_data.to_csv('data/processed/test.csv', index=False)

print("✅ Saved: data/processed/train.csv")
print("✅ Saved: data/processed/val.csv")
print("✅ Saved: data/processed/test.csv")

# ============================================
# PART 10: SAVE VUS DATA (FOR FUTURE PREDICTION)
# ============================================

print("\nExtracting Variants of Uncertain Significance (VUS)...")

vus_data = epilepsy_filtered[
    epilepsy_filtered['ClinicalSignificance'].str.contains(
        'Uncertain significance', 
        case=False, 
        na=False
    )
].copy()

vus_data.to_csv('data/processed/vus_to_classify.csv', index=False)

print(f"🔍 VUS variants to classify: {len(vus_data):,}")
print("✅ Saved: data/processed/vus_to_classify.csv")
print("\n💡 These are perfect for your ML model to predict!")

# ============================================
# PART 11: CREATE GENE-DISEASE MAPPING FOR RAG
# ============================================

print("\nCreating gene-disease mapping for RAG system...")

# Extract unique gene-disease pairs
gene_disease_pairs = epilepsy_filtered[
    ['GeneSymbol', 'PhenotypeList', 'MIM_Number']
].drop_duplicates()

# Count diseases per gene
diseases_per_gene = gene_disease_pairs.groupby('GeneSymbol')['PhenotypeList'].count()
print(f"\n🧬 Diseases per gene:")
print(diseases_per_gene.sort_values(ascending=False).head(10))

# Save for RAG knowledge base
gene_disease_pairs.to_csv('data/knowledge_base/gene_disease_mapping.csv', index=False)
print("\n✅ Saved: data/knowledge_base/gene_disease_mapping.csv")

# ============================================
# PART 12: SUMMARY STATISTICS
# ============================================

print("\n" + "="*60)
print("FINAL SUMMARY")
print("="*60)

summary = {
    'Total epilepsy variants': len(epilepsy_data),
    'After quality filtering': len(epilepsy_filtered),
    'Labeled for ML (Pathogenic/Benign)': len(labeled_data),
    '  - Pathogenic': (labeled_data['Label']==1).sum(),
    '  - Benign': (labeled_data['Label']==0).sum(),
    'VUS (to be classified)': len(vus_data),
    'Unique genes': epilepsy_filtered['GeneSymbol'].nunique(),
    'Unique diseases': gene_disease_pairs['PhenotypeList'].nunique(),
    'Train set size': len(train_data),
    'Validation set size': len(val_data),
    'Test set size': len(test_data),
}

for key, value in summary.items():
    print(f"{key:.<40} {value:,}")

print("\n" + "="*60)
print("✅ DATA PREPARATION COMPLETE!")
print("="*60)

print("\n📁 Files created:")
print("   • data/processed/epilepsy_variants_all.csv")
print("   • data/processed/train.csv")
print("   • data/processed/val.csv")
print("   • data/processed/test.csv")
print("   • data/processed/vus_to_classify.csv")
print("   • data/knowledge_base/gene_disease_mapping.csv")

print("\n🚀 Next steps:")
print("   1. Run: python feature_engineering.py")
print("   2. Run: python train_model.py")
print("   3. Build RAG knowledge base")

# ============================================
# PART 13: SAVE METADATA FOR DOCUMENTATION
# ============================================

metadata = {
    'date_created': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
    'clinvar_source': 'https://ftp.ncbi.nlm.nih.gov/pub/clinvar/',
    'omim_source': 'https://www.omim.org/static/omim/data/mim2gene.txt',
    'epilepsy_genes': EPILEPSY_GENES,
    'total_variants': len(epilepsy_filtered),
    'train_size': len(train_data),
    'val_size': len(val_data),
    'test_size': len(test_data),
    'class_balance': {
        'pathogenic': int((labeled_data['Label']==1).sum()),
        'benign': int((labeled_data['Label']==0).sum())
    }
}

import json
with open('data/processed/metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)

print("\n✅ Metadata saved: data/processed/metadata.json")