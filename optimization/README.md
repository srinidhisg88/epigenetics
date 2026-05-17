# Model Optimization Suite

This directory contains comprehensive hyperparameter optimization notebooks to improve model performance and reduce overfitting.

## 📊 Current Performance Baseline

**XGBoost (Current Best):**
- Train F1: 89.29%
- Validation F1: 84.64%
- Test F1: 85.06%
- **Overfitting Gap: 4.65%** ⚠️

## 🎯 Optimization Goals

1. **Increase Test F1 Score** to >86%
2. **Reduce Overfitting Gap** to <3%
3. **Maintain or Improve AUC-ROC** (>94%)

## 📁 Notebooks Overview

### 1. XGBoost Optimization (`1_xgboost_optimization.ipynb`)
**Purpose:** Fine-tune XGBoost parameters to reduce overfitting while maintaining performance

**Strategies:**
- **Strategy 1:** Regularized Model - Stronger regularization (more pruning, higher min_child_weight)
- **Strategy 2:** Balanced Model - Middle ground approach
- **Strategy 3:** Grid Search - Systematic parameter exploration
- **Strategy 4:** Randomized Search - Broader parameter space exploration

**Key Parameters Tuned:**
- `max_depth`: 6-10 (controls tree complexity)
- `learning_rate`: 0.01-0.1 (slower = better generalization)
- `min_child_weight`: 3-7 (higher = more conservative)
- `gamma`: 0.1-0.4 (pruning threshold)
- `reg_alpha`, `reg_lambda`: L1/L2 regularization
- `subsample`, `colsample_bytree`: Feature randomization

**Expected Runtime:** 15-20 minutes

### 2. Random Forest Optimization (`2_random_forest_optimization.ipynb`)
**Purpose:** Optimize Random Forest to compete with XGBoost

**Strategies:**
- Regularized configuration (more trees, shallower depth)
- Balanced configuration
- Grid search optimization

**Key Parameters Tuned:**
- `n_estimators`: 300-500
- `max_depth`: 12-20
- `min_samples_split`: 10-20
- `min_samples_leaf`: 4-8
- `max_features`: 'sqrt', 'log2'
- `max_samples`: 0.7-0.9 (bootstrap sampling)

**Expected Runtime:** 10-15 minutes

### 3. Ensemble Optimization (`3_ensemble_optimization.ipynb`)
**Purpose:** Combine multiple models for superior performance

**Methods:**
1. **Voting Classifier** - Equal weight averaging
2. **Weighted Voting** - Performance-based weighting
3. **Stacking (LR Meta)** - Logistic Regression meta-learner
4. **Stacking (XGB Meta)** - XGBoost meta-learner

**Base Models Used:**
- XGBoost (optimized)
- Random Forest (optimized)
- Gradient Boosting
- LightGBM

**Expected Runtime:** 20-30 minutes

## 🚀 Quick Start

### Step 1: Run XGBoost Optimization
```bash
# Open Jupyter
jupyter notebook optimization/1_xgboost_optimization.ipynb

# Or use Jupyter Lab
jupyter lab optimization/1_xgboost_optimization.ipynb
```

Execute all cells to:
1. Test multiple XGBoost configurations
2. Run grid and random search
3. Compare all approaches
4. Save the best model

### Step 2: Run Random Forest Optimization
```bash
jupyter notebook optimization/2_random_forest_optimization.ipynb
```

### Step 3: Run Ensemble Optimization
```bash
jupyter notebook optimization/3_ensemble_optimization.ipynb
```

This combines the best models from Steps 1 & 2.

## 📈 Expected Improvements

Based on similar projects, you can expect:

| Metric | Current | After Optimization | Improvement |
|--------|---------|-------------------|-------------|
| Test F1 | 85.06% | **86-88%** | +1-3% |
| Overfitting Gap | 4.65% | **2-3%** | -1.65-2.65% |
| Test AUC | 94.58% | **95-96%** | +0.4-1.4% |

## 🔍 What Each Strategy Does

### Regularization Strategies

1. **Reduce max_depth** (10→7)
   - Makes trees shallower
   - Prevents memorizing training data
   - **Reduces overfitting**

2. **Lower learning_rate** (0.1→0.03-0.05)
   - Smaller steps toward optimum
   - More gradual learning
   - **Better generalization**

3. **Increase min_child_weight** (3→5-6)
   - Requires more samples per leaf
   - More conservative splits
   - **Reduces overfitting**

4. **Increase gamma** (0.1→0.3-0.4)
   - Higher threshold for splits
   - More aggressive pruning
   - **Reduces model complexity**

5. **Add L1/L2 regularization**
   - Penalizes large weights
   - Encourages simpler models
   - **Prevents overfitting**

6. **More subsample/colsample**
   - Uses random subsets of data/features
   - Increases diversity
   - **Improves robustness**

### Ensemble Benefits

- **Reduces variance** - Multiple models average out errors
- **Improves stability** - Less sensitive to data fluctuations
- **Better generalization** - Captures diverse patterns
- **Higher accuracy** - Combines strengths of different algorithms

## 📊 Output Files

After running the notebooks, you'll have:

```
optimization/
├── xgboost_optimization_results.json      # XGBoost results
├── xgboost_comparison.csv                 # XGBoost comparison table
├── xgboost_optimization_results.png       # XGBoost visualizations
├── rf_optimization_results.csv            # RF comparison table
├── ensemble_comparison.csv                # Ensemble comparison table
├── ensemble_optimization_results.json     # Ensemble results
└── ensemble_optimization_results.png      # Ensemble visualizations

models/
├── xgboost_optimized.pkl                  # Best XGBoost model
├── random_forest_optimized.pkl            # Best RF model
└── ensemble_optimized.pkl                 # Best ensemble model
```

## 🎓 Understanding the Results

### How to Interpret Overfitting

```
Good:     Train F1: 87% | Val F1: 85% | Gap: 2%  ✅
Okay:     Train F1: 89% | Val F1: 85% | Gap: 4%  ✓
Warning:  Train F1: 92% | Val F1: 85% | Gap: 7%  ⚠️
Bad:      Train F1: 95% | Val F1: 85% | Gap: 10% ❌
```

### Target Metrics

- **Test F1**: >86% (primary goal)
- **Overfitting Gap**: <3% (acceptable: <5%)
- **Test AUC**: >95% (stretch goal)
- **Balanced Precision/Recall**: Both >84%

## 🔧 Troubleshooting

### If Optimization Makes Things Worse:

1. **Check the comparison tables** - Some configurations may work better
2. **Try the balanced approach** - Not too aggressive on regularization
3. **Use ensemble methods** - Often more stable than single models
4. **Verify data leakage** - Ensure proper train/val/test splits

### If Results Are Similar:

- **This is actually good!** - Means the baseline was already well-tuned
- **Focus on ensembles** - Usually provide 1-2% boost
- **Check for data quality** - Model improvements are limited by data quality

## 💡 Tips for Best Results

1. **Run all three notebooks** - Ensemble combines the best of both worlds
2. **Monitor both metrics** - Don't sacrifice generalization for accuracy
3. **Use the test set sparingly** - Only for final evaluation
4. **Consider the domain** - In medical applications, recall might be more important

## 📚 Next Steps After Optimization

Once you have the best model:

1. ✅ Save the model (done automatically)
2. 📊 Update `model_performance.json` with new metrics
3. 🧪 Run `check_overfitting.py` to verify improvements
4. 🚀 Deploy the optimized model in your application
5. 📝 Document the final parameters for reproducibility

## 🤝 Need Help?

If you encounter issues:
1. Check the error messages in the notebook cells
2. Verify all data files are present
3. Ensure sufficient memory (XGBoost grid search is memory-intensive)
4. Try reducing `n_iter` in RandomizedSearchCV for faster testing

---

**Remember:** The goal is not just high accuracy, but a model that generalizes well to new, unseen data! 🎯
