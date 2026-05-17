"""
Run All ML Model Optimizations
================================
This script runs all optimization strategies sequentially and compares results.

Usage:
    python optimization/run_all_optimizations.py

Note: This will take 45-60 minutes to complete all optimizations.
"""

import subprocess
import sys
from pathlib import Path

print("="*80)
print("EPILEPSY MODEL OPTIMIZATION SUITE")
print("="*80)
print("\nThis will run all optimization notebooks and may take 45-60 minutes.")
print("Press Ctrl+C to cancel at any time.\n")

try:
    input("Press Enter to continue...")
except KeyboardInterrupt:
    print("\n\nCancelled by user.")
    sys.exit(0)

OPTIMIZATION_DIR = Path(__file__).parent
notebooks = [
    "1_xgboost_optimization.ipynb",
    "2_random_forest_optimization.ipynb",
    "3_ensemble_optimization.ipynb"
]

print("\n" + "="*80)
print("STARTING OPTIMIZATION PIPELINE")
print("="*80)

for i, notebook in enumerate(notebooks, 1):
    print(f"\n[{i}/{len(notebooks)}] Running {notebook}...")
    print("-"*80)

    notebook_path = OPTIMIZATION_DIR / notebook

    try:
        # Convert notebook to Python and execute
        result = subprocess.run(
            ["jupyter", "nbconvert", "--to", "notebook", "--execute",
             "--inplace", str(notebook_path)],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutes per notebook
        )

        if result.returncode == 0:
            print(f"✅ {notebook} completed successfully!")
        else:
            print(f"❌ {notebook} failed!")
            print(f"Error: {result.stderr}")

    except subprocess.TimeoutExpired:
        print(f"⏰ {notebook} timed out (>30 minutes)")
    except Exception as e:
        print(f"❌ Error running {notebook}: {e}")

print("\n" + "="*80)
print("OPTIMIZATION PIPELINE COMPLETE!")
print("="*80)

print("\n📁 Results saved in:")
print(f"   - {OPTIMIZATION_DIR}")
print(f"   - ../models/")

print("\n📊 Next steps:")
print("   1. Check optimization results in the notebooks")
print("   2. Review comparison CSVs in optimization/")
print("   3. Load best models from models/ directory")
print("   4. Run check_overfitting.py to verify improvements")

print("\n" + "="*80)
