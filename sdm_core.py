# -*- coding: utf-8 -*-
"""
SDM Core Engine — v2.0
New features:
  - Multicollinearity analysis (VIF + Pearson/Spearman correlation)
  - Variable priority ranking for selection
  - Boyce Index (continuous Boyce index, Hirzel et al. 2006)
  - Extended evaluation: ROC-AUC + TSS + Boyce Index
"""

import os
import warnings
import numpy as np
import pandas as pd
from pathlib import Path

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import PolynomialFeatures, StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.metrics import roc_auc_score
    from sklearn.inspection import permutation_importance
    from sklearn.svm import SVC
    from sklearn.neural_network import MLPClassifier
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from pygam import LogisticGAM, s
    HAS_GAM = True
except ImportError:
    HAS_GAM = False

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    HAS_XGB = False

try:
    import lightgbm as lgb
    HAS_LGB = True
except ImportError:
    HAS_LGB = False

try:
    import catboost as cb
    HAS_CAT = True
except ImportError:
    HAS_CAT = False

try:
    import elapid
    HAS_MAXENT = True
except ImportError:
    HAS_MAXENT = False

try:
    import rasterio
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False


ALGORITHM_INFO = {
    "GLM":    {"label": "GLM     – Generalised Linear Model",       "requires": "scikit-learn", "available": HAS_SKLEARN},
    "GBM":    {"label": "GBM     – Gradient Boosting Machine",      "requires": "scikit-learn", "available": HAS_SKLEARN},
    "BRT":    {"label": "BRT     – Boosted Regression Trees",       "requires": "scikit-learn", "available": HAS_SKLEARN},
    "RF":     {"label": "RF      – Random Forest",                  "requires": "scikit-learn", "available": HAS_SKLEARN},
    "SVM":    {"label": "SVM     – Support Vector Machine",         "requires": "scikit-learn", "available": HAS_SKLEARN},
    "ANN":    {"label": "ANN     – Neural Network (MLP)",           "requires": "scikit-learn", "available": HAS_SKLEARN},
    "XGB":    {"label": "XGBoost – Extreme Gradient Boosting",      "requires": "xgboost",      "available": HAS_XGB},
    "LGB":    {"label": "LightGBM – Light Gradient Boosting",       "requires": "lightgbm",     "available": HAS_LGB},
    "CAT":    {"label": "CatBoost – Categorical Gradient Boosting", "requires": "catboost",     "available": HAS_CAT},
    "GAM":    {"label": "GAM     – Generalised Additive Model",     "requires": "pygam",        "available": HAS_GAM},
    "MAXENT": {"label": "MaxEnt  – Maximum Entropy",                "requires": "elapid",       "available": HAS_MAXENT},
    "ENFA":   {"label": "ENFA    – Ecol. Niche Factor Analysis",   "requires": "scikit-learn", "available": HAS_SKLEARN},
    "MAHAL":  {"label": "Mahalanobis – Distance-Based Niche",      "requires": "scikit-learn", "available": HAS_SKLEARN},
}


def _copy_suitability_qml(tif_path: str) -> None:
    """Copy habitus_suitability.qml next to a .tif so QGIS auto-loads the style."""
    try:
        import shutil, os
        qml_src = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "habitus_suitability.qml")
        if not os.path.isfile(qml_src):
            return
        qml_dst = os.path.splitext(tif_path)[0] + ".qml"
        if not os.path.isfile(qml_dst):
            shutil.copy2(qml_src, qml_dst)
    except Exception:
        pass


def _sanitize_varname(name: str) -> str:
    """
    Convert a raster file stem to a clean Python/pandas column name.

    Rules:
      - Replace spaces, parentheses, hyphens, dots with underscores
      - Collapse multiple underscores into one
      - Strip leading/trailing underscores

    Examples:
      "bio_ (1)"  → "bio_1"
      "bio 5"     → "bio_5"
      "tr-elev"   → "tr_elev"
      "lc.type"   → "lc_type"
    """
    import re
    s = str(name)
    s = re.sub(r"[ \(\)\-\.]+", "_", s)   # special chars → underscore
    s = re.sub(r"_+", "_", s)                  # collapse multiple underscores
    s = s.strip("_")                           # strip leading/trailing
    return s or "var"


# ═══════════════════════════════════════════════════════════════════════════════
# 1. MULTICOLLINEARITY & VARIABLE SELECTION
# ═══════════════════════════════════════════════════════════════════════════════

def compute_vif(df: pd.DataFrame,
                cap: float = 999.0) -> pd.Series:
    """
    Variance Inflation Factor for each column of df.

    VIF(xᵢ) = 1 / (1 − R²ᵢ)
    where R²ᵢ is the coefficient of determination from regressing xᵢ on
    all other columns.

    Interpretation
    --------------
    VIF = 1        : no correlation with other variables
    1 < VIF < 5    : moderate, usually acceptable
    5 ≤ VIF < 10   : high — consider removal (especially for GLM/GAM)
    VIF ≥ 10       : severe multicollinearity (O'Brien 2007)
    VIF = cap (999): near-perfect collinearity — the variable is almost a
                     linear combination of the others (e.g. bio_6 ≈ bio_1 +
                     bio_11 in WorldClim).  Raw values like 10^13 are
                     meaningless — we cap at `cap` and flag the variable.

    Note on floating-point instability
    -----------------------------------
    When R² ≥ 1 − ε (ε ≈ 1e-10), 1/(1−R²) diverges to astronomically
    large values that look like computation errors to users.  We apply a
    conservative tolerance (R² > 0.9999) and cap the result at `cap`.
    The ecological interpretation is identical: the variable is redundant.

    Parameters
    ----------
    df  : DataFrame of predictor values (rows = samples, cols = variables)
    cap : maximum VIF value returned; anything above this is capped
          (default 999 — clearly flags near-perfect collinearity without
          showing scientifically meaningless values like 1.9 × 10¹³)
    """
    from sklearn.linear_model import LinearRegression
    vifs = {}
    cols = list(df.columns)
    X = np.array(df.values, dtype=float, copy=True)

    for i, col in enumerate(cols):
        y_i     = X[:, i]
        X_other = np.delete(X, i, axis=1)
        mask    = np.isfinite(y_i) & np.all(np.isfinite(X_other), axis=1)

        if mask.sum() < 10:
            vifs[col] = np.nan
            continue

        lr     = LinearRegression().fit(X_other[mask], y_i[mask])
        ss_res = np.sum((y_i[mask] - lr.predict(X_other[mask])) ** 2)
        ss_tot = np.sum((y_i[mask] - y_i[mask].mean()) ** 2)

        if ss_tot <= 0:
            # Constant variable — VIF undefined
            vifs[col] = np.nan
            continue

        r2 = 1.0 - ss_res / ss_tot

        # Clamp R² to [0, 1] to guard against floating-point overshoot
        r2 = max(0.0, min(r2, 1.0))

        # Near-perfect collinearity threshold: R² > 0.9999
        # → 1/(1-R²) > 10 000, which is already far beyond any SDM
        #   relevance.  Cap to avoid confusing astronomic values.
        if r2 > 0.9999:
            vifs[col] = cap
        else:
            vifs[col] = min(1.0 / (1.0 - r2), cap)

    return pd.Series(vifs)


def compute_correlation_matrix(df: pd.DataFrame, method: str = "pearson") -> pd.DataFrame:
    """Pearson or Spearman correlation matrix."""
    return df.corr(method=method)


def variable_priority_ranking(df: pd.DataFrame,
                               y: np.ndarray,
                               vif_threshold: float = 10.0,
                               corr_threshold: float = 0.70,
                               method: str = "pearson") -> pd.DataFrame:
    """
    Rank variables by priority for SDM modelling.

    Steps:
    1. Compute VIF – flag variables with VIF > threshold
    2. Compute correlation – identify highly correlated pairs
    3. Score each variable: higher = more important/less collinear
       Score = (1/VIF) * 0.5 + (1 - mean_abs_corr_with_others) * 0.5
    4. For correlated pairs, keep the one with lower VIF / higher univariate AUC

    Returns DataFrame with columns:
      Variable, VIF, Mean_Corr, Univariate_AUC, Priority_Score,
      VIF_OK, Corr_OK, Recommended
    """
    from sklearn.metrics import roc_auc_score

    vars_ = list(df.columns)
    n = len(vars_)
    X = df.values.astype(float)

    # VIF
    vif_series = compute_vif(df)

    # Correlation matrix — copy array before fill_diagonal (pandas .values can be read-only)
    corr_df   = compute_correlation_matrix(df, method=method).abs()
    corr_arr  = corr_df.values.copy()          # writable copy
    np.fill_diagonal(corr_arr, 0)              # zero out self-correlations
    corr_mat  = pd.DataFrame(corr_arr, index=corr_df.index, columns=corr_df.columns)
    mean_corr = corr_mat.mean(axis=1)

    # Univariate AUC (simple logistic or rank-based)
    uni_auc = {}
    for col in vars_:
        x_col = df[col].values
        mask = np.isfinite(x_col) & np.isfinite(y)
        if mask.sum() < 10:
            uni_auc[col] = 0.5
            continue
        try:
            uni_auc[col] = roc_auc_score(y[mask].astype(int), x_col[mask])
            if uni_auc[col] < 0.5:
                uni_auc[col] = 1.0 - uni_auc[col]  # flip if inversely related
        except Exception:
            uni_auc[col] = 0.5

    # Priority score (0–1)
    vif_norm = vif_series.clip(upper=50)
    vif_score = 1.0 - (vif_norm - 1.0) / 49.0
    corr_score = 1.0 - mean_corr
    auc_score  = pd.Series({v: uni_auc[v] for v in vars_})
    priority   = (vif_score * 0.35 + corr_score * 0.35 + (auc_score - 0.5) * 0.30).clip(0, 1)

    # Flags
    # VIF=999 = capped near-perfect collinearity — always flag regardless of threshold
    vif_ok  = (vif_series <= vif_threshold) & (vif_series < 999)
    corr_ok = mean_corr < corr_threshold

    # Recommended: VIF OK AND corr OK, OR top-ranked even if borderline
    recommended = vif_ok & corr_ok

    # Identify correlated pairs to help user choose
    high_corr_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            c = corr_mat.iloc[i, j]
            if c >= corr_threshold:
                high_corr_pairs.append((vars_[i], vars_[j], round(float(c), 3)))

    result = pd.DataFrame({
        "Variable":       vars_,
        "VIF":            [round(float(vif_series[v]), 2) for v in vars_],
        "Mean_Corr":      [round(float(mean_corr[v]), 3) for v in vars_],
        "Univariate_AUC": [round(float(uni_auc[v]), 3) for v in vars_],
        "Priority_Score": [round(float(priority[v]), 3) for v in vars_],
        "VIF_OK":         [bool(vif_ok[v]) for v in vars_],
        "Corr_OK":        [bool(corr_ok[v]) for v in vars_],
        "Recommended":    [bool(recommended[v]) for v in vars_],
    }).sort_values("Priority_Score", ascending=False).reset_index(drop=True)

    result.attrs["high_corr_pairs"] = high_corr_pairs
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# 2. BOYCE INDEX  (Hirzel et al. 2006)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_boyce_index(y_true: np.ndarray,
                         y_prob: np.ndarray,
                         n_bins: int = 101,
                         window_width: float = 0.1) -> dict:
    """
    Continuous Boyce Index (CBI).

    Measures how much a habitat suitability model differs from a random
    distribution of observed presences.  Ranges from −1 to +1:
      CBI > 0.5  → good predictive model
      CBI ≈ 0    → no better than random
      CBI < 0    → counter-useful (high scores where species is absent)

    Parameters
    ----------
    y_true       : 1-D array, 0/1 labels (1 = presence)
    y_prob       : predicted suitability / probability in [0, 1]
    n_bins        : number of evaluation points along the [0,1] axis.
                   Default 101 (= 0.01 resolution) following Hirzel et al.
                   (2006) who used 100 bins across the full suitability range.
    window_width : width of the sliding window as a fraction of [0,1].
                   Default 0.1 (= 10% of the suitability axis), consistent
                   with Hirzel et al. (2006) and the PresenceAbsence R package
                   implementation.  Smaller values increase resolution but
                   increase noise; larger values smooth the F-ratio curve.

    Returns
    -------
    dict with keys:
      'boyce'       : CBI value (Spearman ρ of bin-centre vs F-ratio)
      'bin_centers' : suitability values at each evaluation bin
      'F_ratio'     : observed/expected frequency ratio per bin

    References
    ----------
    Hirzel, A.H., Le Lay, G., Helfer, V., Randin, C., Guisan, A. (2006).
    Evaluating the ability of habitat suitability models to predict
    species presences. Ecological Modelling 199:142–152.
    https://doi.org/10.1016/j.ecolmodel.2006.05.017

    Boyce, M.S., Vernier, P.R., Nielsen, S.E., Schmiegelow, F.K. (2002).
    Evaluating resource selection functions. Ecological Modelling 157:281–300.
    """
    pres_idx = y_true == 1
    pres_probs = y_prob[pres_idx]
    all_probs  = y_prob

    if pres_probs.sum() == 0 or len(all_probs) < 5:
        return {"boyce": np.nan, "bin_centers": np.array([]), "F_ratio": np.array([])}

    bin_centers = np.linspace(0, 1, n_bins)
    half_w = window_width / 2.0

    predicted_ratio = []
    valid_centers   = []

    for center in bin_centers:
        lo, hi = center - half_w, center + half_w
        n_pres_bin = np.sum((pres_probs >= lo) & (pres_probs < hi))
        n_all_bin  = np.sum((all_probs  >= lo) & (all_probs  < hi))

        if n_all_bin == 0:
            continue

        # Expected = proportion of all points in bin × total presences
        exp = (n_all_bin / len(all_probs)) * len(pres_probs)
        if exp == 0:
            continue

        predicted_ratio.append(n_pres_bin / exp)
        valid_centers.append(center)

    if len(valid_centers) < 3:
        return {"boyce": np.nan, "bin_centers": np.array([]), "F_ratio": np.array([])}

    centers = np.array(valid_centers)
    ratios  = np.array(predicted_ratio)

    # Spearman correlation between bin center and F-ratio
    from scipy.stats import spearmanr
    try:
        cbi, _ = spearmanr(centers, ratios)
    except Exception:
        # Fallback: manual Spearman
        n = len(centers)
        rank_c = np.argsort(np.argsort(centers)).astype(float)
        rank_r = np.argsort(np.argsort(ratios)).astype(float)
        d2 = np.sum((rank_c - rank_r) ** 2)
        cbi = 1.0 - 6.0 * d2 / (n * (n ** 2 - 1))

    return {
        "boyce":       round(float(cbi), 4),
        "bin_centers": centers,
        "F_ratio":     ratios,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. EVALUATION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def compute_tss(y_true, y_prob, threshold=0.5):
    y_pred = (y_prob >= threshold).astype(int)
    tp = np.sum((y_true == 1) & (y_pred == 1))
    fn = np.sum((y_true == 1) & (y_pred == 0))
    fp = np.sum((y_true == 0) & (y_pred == 1))
    tn = np.sum((y_true == 0) & (y_pred == 0))
    sens = tp / (tp + fn) if (tp + fn) > 0 else 0
    spec = tn / (tn + fp) if (tn + fp) > 0 else 0
    return sens + spec - 1


def find_optimal_threshold(y_true, y_prob, method="max_tss"):
    """
    Find the optimal suitability threshold for converting continuous
    predictions to binary presence/absence maps.

    Parameters
    ----------
    method : str
        "max_tss"      — Maximise True Skill Statistic (Sensitivity+Specificity−1).
                         Standard in SDM; threshold-independent of prevalence.
                         Allouche et al. (2006) J. Appl. Ecology 43:1223-1232.

        "max_kappa"    — Maximise Cohen's Kappa.
                         Prevalence-sensitive but widely reported.
                         Fielding & Bell (1997) Environ. Conserv. 24:38-49.

        "sens_spec_eq" — Equal sensitivity and specificity (sens = spec).
                         Recommended when commission and omission errors are
                         equally important.  Liu et al. (2005) Ecography 28:385-393.

        "p10"          — 10th percentile of predicted values at presence sites.
                         Minimal predicted area threshold: excludes only the
                         10% of presences with the lowest predicted suitability.
                         Commonly used with MaxEnt (Pearson et al. 2007).

        "min_roi"      — Minimum ROC point closest to (0,1): minimises
                         Euclidean distance from the perfect classifier.
                         Threshold-independent of prevalence.

    Returns
    -------
    threshold : float
    metric_value : float
    """
    y_true = np.array(y_true, dtype=int)
    y_prob = np.array(y_prob, dtype=float)

    if method == "p10":
        pres_probs = y_prob[y_true == 1]
        if len(pres_probs) == 0:
            return 0.5, 0.0
        thr = float(np.percentile(pres_probs, 10))
        tss = compute_tss(y_true, y_prob, thr)
        return thr, tss

    thresholds = np.linspace(0.01, 0.99, 200)

    if method == "max_tss":
        best_val, best_thr = -1.0, 0.5
        for thr in thresholds:
            t = compute_tss(y_true, y_prob, thr)
            if t > best_val:
                best_val, best_thr = t, thr
        return best_thr, best_val

    elif method == "max_kappa":
        best_val, best_thr = -1.0, 0.5
        for thr in thresholds:
            y_pred = (y_prob >= thr).astype(int)
            n = len(y_true)
            tp = int(((y_true==1) & (y_pred==1)).sum())
            tn = int(((y_true==0) & (y_pred==0)).sum())
            fp = int(((y_true==0) & (y_pred==1)).sum())
            fn = int(((y_true==1) & (y_pred==0)).sum())
            po  = (tp + tn) / n if n > 0 else 0
            pe  = ((tp+fp)*(tp+fn) + (tn+fn)*(tn+fp)) / (n*n) if n > 0 else 0
            kappa = (po - pe) / (1 - pe) if (1 - pe) > 1e-9 else 0
            if kappa > best_val:
                best_val, best_thr = kappa, thr
        return best_thr, best_val

    elif method == "sens_spec_eq":
        best_diff, best_thr = 1.0, 0.5
        for thr in thresholds:
            y_pred = (y_prob >= thr).astype(int)
            tp = int(((y_true==1) & (y_pred==1)).sum())
            tn = int(((y_true==0) & (y_pred==0)).sum())
            fp = int(((y_true==0) & (y_pred==1)).sum())
            fn = int(((y_true==1) & (y_pred==0)).sum())
            sens = tp / (tp + fn) if (tp+fn) > 0 else 0
            spec = tn / (tn + fp) if (tn+fp) > 0 else 0
            diff = abs(sens - spec)
            if diff < best_diff:
                best_diff, best_thr = diff, thr
        tss = compute_tss(y_true, y_prob, best_thr)
        return best_thr, tss

    elif method == "min_roi":
        try:
            from sklearn.metrics import roc_curve
            fpr, tpr, thr_arr = roc_curve(y_true, y_prob)
            dist = np.sqrt(fpr**2 + (1 - tpr)**2)
            idx  = int(np.argmin(dist))
            thr  = float(thr_arr[min(idx, len(thr_arr)-1)])
            tss  = compute_tss(y_true, y_prob, thr)
            return thr, tss
        except Exception:
            return find_optimal_threshold(y_true, y_prob, "max_tss")

    else:
        return find_optimal_threshold(y_true, y_prob, "max_tss")


def find_tss_threshold(y_true, y_prob, steps=100):
    """Backward-compatible wrapper → max_tss method."""
    thr, tss = find_optimal_threshold(y_true, y_prob, "max_tss")
    return thr, tss


def compute_roc_auc(y_true, y_prob):
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)
    if len(np.unique(y_true)) < 2:
        return np.nan
    try:
        return float(roc_auc_score(y_true, y_prob))
    except Exception:
        return np.nan


def evaluate_all(y_true, y_prob, threshold_method="max_tss"):
    """Return dict with ROC, TSS and Boyce for a model prediction."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob, dtype=float)

    # Guard: need both classes to evaluate
    n_pos = int((y_true == 1).sum())
    n_neg = int((y_true == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return {"ROC": np.nan, "TSS": np.nan, "Boyce": np.nan,
                "_thr": 0.5, "_thr_method": threshold_method,
                "_boyce_detail": {"boyce": np.nan}}

    roc = compute_roc_auc(y_true, y_prob)
    try:
        thr, tss = find_optimal_threshold(y_true, y_prob, method=threshold_method)
    except Exception:
        thr, tss = 0.5, np.nan
    try:
        boyce_result = compute_boyce_index(y_true, y_prob)
    except Exception:
        boyce_result = {"boyce": np.nan}
    return {
        "ROC":   roc,
        "TSS":   tss,
        "Boyce": boyce_result.get("boyce", np.nan),
        "_thr":  thr,
        "_thr_method": threshold_method,
        "_boyce_detail": boyce_result,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. DATA FORMATTING  (≈ BIOMOD_FormatingData)
# ═══════════════════════════════════════════════════════════════════════════════

class DataFormatter:
    def __init__(self, presence_csv, env_rasters,
                 species_col="presence", lon_col="long", lat_col="lat",
                 # ML pseudo-absence params
                 n_pa_rep=2, n_absences=1000, pa_strategy="random",
                 pa_min_dist_km=0.0,
                 # MaxEnt background params
                 n_background=10000, mx_bg_strategy="random",
                 mx_min_dist_km=0.0, mx_bias_correct=False,
                 # Presence-only background (ENFA / Mahalanobis)
                 ponly_use_bg=True, ponly_n_bg=5000,
                 ponly_strategy="random", ponly_min_dist_km=0.0,
                 # Categorical raster params
                 cat_rasters=None, cat_encoding="one-hot",
                 progress_callback=None):
        self.presence_csv    = presence_csv
        self.env_rasters     = env_rasters          # continuous rasters
        self.cat_rasters     = cat_rasters or []    # categorical rasters
        self.cat_encoding    = cat_encoding         # "one-hot"|"label"|"target"
        self.species_col     = species_col
        self.lon_col         = lon_col
        self.lat_col         = lat_col
        # ML
        self.n_pa_rep        = n_pa_rep
        self.n_absences      = n_absences
        self.pa_strategy     = pa_strategy
        self.pa_min_dist_km  = pa_min_dist_km
        # MaxEnt background
        self.n_background    = n_background
        self.mx_bg_strategy  = mx_bg_strategy
        self.mx_min_dist_km  = mx_min_dist_km
        self.mx_bias_correct = mx_bias_correct
        # Presence-only background
        self.ponly_use_bg     = ponly_use_bg
        self.ponly_n_bg       = ponly_n_bg
        self.ponly_strategy   = ponly_strategy
        self.ponly_min_dist_km= ponly_min_dist_km
        self.progress_cb     = progress_callback or (lambda m, p: None)

        self.occ_df           = None
        self.env_data         = {}    # continuous: {varname: 2D array}
        self.cat_data         = {}    # categorical: {varname: 2D int array}
        self.cat_classes      = {}    # {varname: sorted list of unique classes}
        self.raster_meta      = None
        self.pa_datasets      = []
        self.var_names        = []    # continuous variable names
        self.cat_var_names    = []    # categorical variable names (before encoding)
        self.encoded_cat_names= []    # after one-hot: ["lc_1","lc_2",...] etc.
        self.background_X      = None
        self.background_coords = None
        self.background_ponly  = None   # for ENFA / Mahalanobis
        self.collinearity_df  = None
        # Points removed before modelling — populated by generate_pa_datasets()
        # Each entry: {"lon": float, "lat": float, "reason": str}
        self.dropped_points   = []

    def load_data(self):
        self.progress_cb("Loading occurrence data…", 5)
        self.occ_df = pd.read_csv(self.presence_csv)

        # ── Extract species name from first column ────────────────────────────
        import re as _re
        first_col = self.occ_df.columns[0]
        # Use first column if it is NOT the lon/lat/presence column
        if first_col not in (self.lon_col, self.lat_col, self.species_col):
            vals = self.occ_df[first_col].dropna().astype(str)
            if len(vals) > 0:
                from collections import Counter as _Ctr
                candidate = _Ctr(vals).most_common(1)[0][0]
                cleaned = _re.sub(r'[^\w\s.-]', '', candidate).replace('_', ' ')
                self.species_name = ' '.join(cleaned.split()) or "species"
            else:
                self.species_name = "species"
        else:
            # Fall back: use CSV filename stem (replace underscores/dashes with spaces)
            stem = Path(self.presence_csv).stem
            self.species_name = _re.sub(r'[_\-]+', ' ', stem).strip() or "species"

        self.progress_cb("Loading continuous environmental rasters…", 12)
        self.env_data = {}
        import rasterio as rio
        for rpath in self.env_rasters:
            with rio.open(rpath) as src:
                band = src.read(1).astype(float)
                nd = src.nodata
                if nd is not None:
                    band[band == nd] = np.nan
                vname = _sanitize_varname(Path(rpath).stem)
                self.env_data[vname] = band
                if self.raster_meta is None:
                    self.raster_meta = src.meta.copy()
                    self.transform   = src.transform
                    self.shape       = band.shape

        # ── Categorical rasters ───────────────────────────────────────────
        if self.cat_rasters:
            self.progress_cb(
                f"Loading {len(self.cat_rasters)} categorical raster(s)…", 18)
            self.cat_data = {}
            for rpath in self.cat_rasters:
                with rio.open(rpath) as src:
                    # Read as integer — categorical values must be class codes
                    band = src.read(1)
                    nd   = src.nodata
                    # Use -9999 as sentinel for nodata in integer arrays
                    band_int = band.astype(np.int32)
                    if nd is not None:
                        band_int[band == nd] = -9999
                    vname = _sanitize_varname(Path(rpath).stem)
                    self.cat_data[vname] = band_int
                    # Discover unique classes (exclude nodata sentinel)
                    unique = sorted(set(band_int[band_int != -9999].ravel().tolist()))
                    self.cat_classes[vname] = unique
                    self.progress_cb(
                        f"  {vname}: {len(unique)} classes "
                        f"({unique[:5]}{'…' if len(unique)>5 else ''})", 19)
            self.cat_var_names = list(self.cat_data.keys())
        else:
            self.cat_data      = {}
            self.cat_classes   = {}
            self.cat_var_names = []

    def _coords_to_pixels(self, lons, lats):
        from rasterio.transform import rowcol
        return rowcol(self.transform, lons, lats)

    def _extract_env(self, lons, lats):
        """Extract continuous + encoded categorical values at given coordinates."""
        rows, cols = self._coords_to_pixels(lons, lats)
        rows, cols = np.array(rows), np.array(cols)
        n_rows, n_cols = self.shape
        valid = (rows >= 0) & (rows < n_rows) & (cols >= 0) & (cols < n_cols)
        result = {}

        # ── Continuous variables ──────────────────────────────────────────
        for vname, arr in self.env_data.items():
            vals = np.full(len(lons), np.nan)
            vals[valid] = arr[rows[valid], cols[valid]]
            result[vname] = vals

        # ── Categorical variables — always label encode ─────────────────
        # Label encoding: keep integer class code as a single column.
        # One-hot encoding is avoided because:
        #   - It explodes feature count (40 classes → 40 columns)
        #   - Tree models (RF, XGB, LGB, CatBoost) handle integers natively
        #   - MaxEnt uses the integer as a continuous feature (acceptable)
        #   - GLM/SVM/ANN users should be aware of this limitation
        for vname, arr in self.cat_data.items():
            raw = np.full(len(lons), -9999, dtype=np.int32)
            raw[valid] = arr[rows[valid], cols[valid]]
            vals = raw.astype(float)
            vals[raw == -9999] = np.nan
            result[vname] = vals

        return pd.DataFrame(result)

    def _filter_presence_points(self, lons, lats):
        """Remove presence points that are duplicated, outside the raster extent,
        or fall on NoData cells.

        Populates self.dropped_points with per-point reason strings and returns
        filtered (lons, lats) arrays containing only usable points.
        """
        from rasterio.transform import rowcol as _rowcol

        self.dropped_points = []
        lons = np.array(lons, dtype=float)
        lats = np.array(lats, dtype=float)
        n_total = len(lons)

        # ── 1) Duplicate coordinates ──────────────────────────────────────────
        seen_coords = {}   # (lon_rounded, lat_rounded) → first index
        dup_mask = np.zeros(n_total, dtype=bool)
        for i, (lo, la) in enumerate(zip(lons, lats)):
            key = (round(float(lo), 8), round(float(la), 8))
            if key in seen_coords:
                dup_mask[i] = True
                self.dropped_points.append({
                    "lon": float(lo), "lat": float(la),
                    "reason": "duplicate coordinate",
                })
            else:
                seen_coords[key] = i

        # Work only on non-duplicate points for the remaining checks
        candidates = ~dup_mask
        c_lons = lons[candidates]
        c_lats = lats[candidates]
        c_idx  = np.where(candidates)[0]   # original indices

        # ── 2) Outside raster extent ──────────────────────────────────────────
        n_rows, n_cols = self.shape
        rows, cols = _rowcol(self.transform, c_lons, c_lats)
        rows = np.array(rows, dtype=int)
        cols = np.array(cols, dtype=int)
        in_extent = (rows >= 0) & (rows < n_rows) & (cols >= 0) & (cols < n_cols)

        for j, orig_i in enumerate(c_idx):
            if not in_extent[j]:
                self.dropped_points.append({
                    "lon": float(lons[orig_i]), "lat": float(lats[orig_i]),
                    "reason": "outside raster extent",
                })

        # ── 3) Within extent but any continuous env value is NoData ──────────
        nodata_mask = np.zeros(len(c_lons), dtype=bool)
        for j in np.where(in_extent)[0]:
            r, c = rows[j], cols[j]
            if any(np.isnan(arr[r, c]) for arr in self.env_data.values()):
                nodata_mask[j] = True
                self.dropped_points.append({
                    "lon": float(c_lons[j]), "lat": float(c_lats[j]),
                    "reason": "falls on NoData cell",
                })

        # ── Build final keep mask on original array ───────────────────────────
        keep = np.zeros(n_total, dtype=bool)
        for j, orig_i in enumerate(c_idx):
            if in_extent[j] and not nodata_mask[j]:
                keep[orig_i] = True

        n_dropped = int((~keep).sum())
        n_kept    = int(keep.sum())
        n_dup     = int(dup_mask.sum())
        n_ext     = sum(1 for p in self.dropped_points
                        if p["reason"] == "outside raster extent")
        n_nd      = sum(1 for p in self.dropped_points
                        if p["reason"] == "falls on NoData cell")

        if n_dropped:
            parts = []
            if n_dup: parts.append(f"{n_dup} duplicate(s)")
            if n_ext: parts.append(f"{n_ext} outside extent")
            if n_nd:  parts.append(f"{n_nd} on NoData")
            self.progress_cb(
                f"⚠  {n_dropped} of {n_total} presence point(s) removed "
                f"({', '.join(parts)}) — {n_kept} point(s) retained.", 27)
        else:
            self.progress_cb(
                f"✔  All {n_total} presence points are valid "
                f"(no duplicates, all within raster extent).", 27)

        if n_kept < 3:
            raise ValueError(
                f"Only {n_kept} valid presence point(s) remain after removing "
                f"{n_dropped} invalid point(s). At least 3 are required.\n"
                f"Check that your occurrence CSV and rasters share the same CRS.")

        return lons[keep], lats[keep]

    def _apply_target_encoding(self, X_df: pd.DataFrame,
                                y_arr: np.ndarray) -> pd.DataFrame:
        """
        Replace _cat_raw_<vname> columns with target-mean encoding.
        Target encoding: each class → mean presence rate in training data.
        Falls back to global mean for unseen classes (Micci-Barreca 2001).
        """
        global_mean = float(y_arr.mean()) if len(y_arr) > 0 else 0.5
        raw_cols = [c for c in X_df.columns if c.startswith("_cat_raw_")]
        for raw_col in raw_cols:
            vname = raw_col[len("_cat_raw_"):]
            encoded_col = vname
            classes = self.cat_classes.get(vname, [])
            class_means = {}
            for cls in classes:
                mask = (X_df[raw_col] == cls)
                if mask.sum() > 0:
                    class_means[cls] = float(y_arr[mask].mean())
                else:
                    class_means[cls] = global_mean
            X_df[encoded_col] = X_df[raw_col].map(
                lambda v: class_means.get(int(v), global_mean)
                          if not np.isnan(v) else np.nan)
            X_df = X_df.drop(columns=[raw_col])
        return X_df

    def get_all_feature_names(self) -> list:
        """Return all feature column names after encoding."""
        names = list(self.var_names)  # continuous
        for vname in self.cat_var_names:
            if self.cat_encoding == "label":
                names.append(vname)
            elif self.cat_encoding == "target":
                names.append(vname)
            else:  # one-hot
                for cls in self.cat_classes.get(vname, []):
                    names.append(f"{vname}_{cls}")
        return names

    # ── SRE yardımcısı ───────────────────────────────────────────────────────
    def _compute_sre_mask(self, pres_env_df: pd.DataFrame,
                           quantile_cut: float = 0.05) -> np.ndarray:
        """
        Surface Range Envelope (SRE) mask.

        Implements the bioclimatic envelope approach of Busby (1991) and
        Nix (1986): a cell is inside the envelope if ALL environmental
        variables fall within the [q, 1-q] quantile range observed at
        presence locations.  Points outside this envelope are candidate
        pseudo-absence / background cells (they are clearly outside the
        known ecological range of the species).

        Parameters
        ----------
        pres_env_df   : DataFrame of env values at presence locations
        quantile_cut  : tail fraction to trim (default 0.05 → 5th–95th
                        percentile, following Thuiller et al. 2003)

        Returns
        -------
        2-D boolean mask (same shape as raster) — True = OUTSIDE envelope
        (= valid candidate for pseudo-absence)

        References
        ----------
        Busby (1991) BIOCLIM. Nature Conservation: Cost-Effective Surveys.
        Nix (1986) BIOCLIM: a bioclimatic analysis and prediction system.
        Thuiller et al. (2003) Ecography 26:690–701.
        """
        outside = np.ones(self.shape, dtype=bool)
        for vname, arr in self.env_data.items():
            if vname not in pres_env_df.columns:
                continue
            col = pres_env_df[vname].dropna()
            if len(col) < 4:
                continue
            lo = col.quantile(quantile_cut)
            hi = col.quantile(1.0 - quantile_cut)
            # Cell is INSIDE envelope on this variable
            inside_var = (arr >= lo) & (arr <= hi) & np.isfinite(arr)
            # Cell must be outside on AT LEAST ONE variable to be outside SRE
            # (here we build intersection: inside = inside on ALL vars)
            outside &= ~inside_var  # accumulate: outside if outside any var
        # Correct logic: outside envelope = outside on all vars
        # Redo: inside envelope = inside on ALL vars; outside = NOT inside
        inside_all = np.ones(self.shape, dtype=bool)
        for vname, arr in self.env_data.items():
            if vname not in pres_env_df.columns:
                continue
            col = pres_env_df[vname].dropna()
            if len(col) < 4:
                continue
            lo = col.quantile(quantile_cut)
            hi = col.quantile(1.0 - quantile_cut)
            inside_all &= (arr >= lo) & (arr <= hi) & np.isfinite(arr)
        return ~inside_all   # True = outside SRE = candidate PA cell

    def _sample_background(self, n, min_dist_km=0.0,
                            pres_lons=None, pres_lats=None,
                            strategy="random",
                            sre_mask=None,
                            bias_weights=None):
        """
        Sample n background / pseudo-absence points from valid raster cells.

        Parameters
        ----------
        n             : number of points to sample
        min_dist_km   : minimum distance from any presence (disk strategy)
        pres_lons/lats: presence coordinates for distance filtering
        strategy      : "random" | "disk" | "sre"
                        - random: uniform random (Barbet-Massin et al. 2012)
                        - disk: minimum distance from presences
                        - sre: only cells outside the bioclimatic envelope
                               (Thuiller et al. 2003; reduces spatial bias)
        sre_mask      : precomputed SRE mask (True = outside envelope)
        bias_weights  : 1-D array of sampling weights for bias correction
                        (Phillips & Dudík 2008 target-group approach).
                        Length must equal number of valid cells.

        References
        ----------
        Barbet-Massin et al. (2012) Methods Ecol. Evol. 3:405-412.
        Phillips & Dudík (2008) Ecography 31:272-278.
        Thuiller et al. (2003) Ecography 26:690-701.
        """
        stacked    = np.stack(list(self.env_data.values()), axis=0)
        valid_mask = np.all(np.isfinite(stacked), axis=0)

        # Apply SRE mask: only use cells outside the bioclimatic envelope
        if strategy == "sre" and sre_mask is not None:
            valid_mask = valid_mask & sre_mask
            if valid_mask.sum() == 0:
                warnings.warn(
                    "SRE strategy: no cells outside the envelope found. "
                    "Falling back to random sampling.")
                valid_mask = np.all(np.isfinite(stacked), axis=0)

        valid_idx = np.argwhere(valid_mask)
        if len(valid_idx) == 0:
            raise RuntimeError("No valid background cells found.")

        import rasterio.transform as rt
        xs_all, ys_all = rt.xy(self.transform,
                                valid_idx[:, 0], valid_idx[:, 1])
        xs_all = np.array(xs_all); ys_all = np.array(ys_all)

        # Disk strategy: exclude cells within min_dist_km of any presence
        if min_dist_km > 0 and pres_lons is not None and pres_lats is not None:
            min_dist_deg = min_dist_km / 111.0
            keep = np.ones(len(xs_all), dtype=bool)
            for px, py in zip(pres_lons, pres_lats):
                dist = np.sqrt((xs_all - px)**2 + (ys_all - py)**2)
                keep &= dist > min_dist_deg
            xs_all = xs_all[keep]; ys_all = ys_all[keep]
            if bias_weights is not None:
                bias_weights = bias_weights[keep]
            if len(xs_all) == 0:
                raise RuntimeError(
                    f"No background cells remain after min_dist={min_dist_km} km. "
                    "Reduce the minimum distance.")

        # Bias correction: weight sampling by inverse-distance to presence
        # records (target-group approach, Phillips & Dudík 2008)
        p = None
        if bias_weights is not None and len(bias_weights) == len(xs_all):
            bw = np.array(bias_weights, dtype=float)
            bw = np.where(np.isfinite(bw) & (bw > 0), bw, 1e-9)
            p = bw / bw.sum()

        chosen_idx = np.random.choice(
            len(xs_all), size=min(n, len(xs_all)), replace=False, p=p)
        return xs_all[chosen_idx], ys_all[chosen_idx]

    def generate_pa_datasets(self):
        """
        Generate:
          1. n_pa_rep pseudo-absence datasets for ML models (y=0/1)
          2. One background dataset for MaxEnt (env values only, no y labels)
        """
        self.progress_cb("Generating pseudo-absences for ML models…", 28)
        # Validate that lon/lat columns exist in the dataframe
        if self.lon_col not in self.occ_df.columns:
            avail = ", ".join(self.occ_df.columns.tolist())
            raise KeyError(
                f"Longitude column '{self.lon_col}' not found in CSV. "
                f"Available columns: {avail}. "
                f"Check the Longitude column setting in the Data tab.")
        if self.lat_col not in self.occ_df.columns:
            avail = ", ".join(self.occ_df.columns.tolist())
            raise KeyError(
                f"Latitude column '{self.lat_col}' not found in CSV. "
                f"Available columns: {avail}. "
                f"Check the Latitude column setting in the Data tab.")
        pres_lons = self.occ_df[self.lon_col].values.astype(float)
        pres_lats = self.occ_df[self.lat_col].values.astype(float)

        # ── Filter invalid presence points before modelling ───────────────────
        pres_lons, pres_lats = self._filter_presence_points(pres_lons, pres_lats)
        # ─────────────────────────────────────────────────────────────────────

        pres_env  = self._extract_env(pres_lons, pres_lats)
        pres_y    = np.ones(len(pres_lons))

        # Precompute SRE mask if strategy == "sre"
        sre_mask = None
        if self.pa_strategy == "sre":
            self.progress_cb("Computing SRE bioclimatic envelope…", 30)
            try:
                sre_mask = self._compute_sre_mask(
                    pres_env, quantile_cut=0.05)
                n_outside = sre_mask.sum()
                self.progress_cb(
                    f"SRE: {n_outside:,} cells outside envelope "
                    f"({100*n_outside/sre_mask.size:.1f}% of study area).", 32)
            except Exception as e:
                warnings.warn(f"SRE computation failed, falling back to random: {e}")
                sre_mask = None

        self.pa_datasets = []
        for rep in range(self.n_pa_rep):
            self.progress_cb(
                f"PA repetition {rep+1}/{self.n_pa_rep} "
                f"({self.pa_strategy}, n={self.n_absences})…",
                33 + rep * 6)
            abs_lons, abs_lats = self._sample_background(
                self.n_absences,
                min_dist_km = self.pa_min_dist_km
                              if self.pa_strategy == "disk" else 0.0,
                pres_lons   = pres_lons,
                pres_lats   = pres_lats,
                strategy    = self.pa_strategy,
                sre_mask    = sre_mask,
            )
            abs_env = self._extract_env(abs_lons, abs_lats)
            abs_y   = np.zeros(len(abs_lons))
            X = pd.concat([pres_env, abs_env], ignore_index=True)
            y = np.concatenate([pres_y, abs_y])
            coords = {
                "lon": np.concatenate([pres_lons, abs_lons]),
                "lat": np.concatenate([pres_lats, abs_lats]),
            }
            valid = X.notna().all(axis=1).values
            self.pa_datasets.append((X[valid], y[valid],
                                     {k: v[valid] for k, v in coords.items()}))

        # ── MaxEnt background points (separate from PA) ──────────────────
        # Bias correction: Phillips & Dudík (2008) target-group approach.
        # Weights background cells by proximity to presence records,
        # correcting for uneven sampling effort in occurrence databases.
        self.progress_cb(
            f"Generating MaxEnt background points "
            f"(n={self.n_background}, strategy={self.mx_bg_strategy}"
            f"{', bias-corrected' if self.mx_bias_correct else ''})…", 44)
        try:
            # Build bias weights if requested
            bias_weights_bg = None
            if self.mx_bias_correct:
                try:
                    # Kernel density of presence records → sampling weight
                    # Cells near many presences → higher weight
                    # (simulates target-group background, Phillips & Dudík 2008)
                    stacked = np.stack(list(self.env_data.values()), axis=0)
                    valid_mask_bg = np.all(np.isfinite(stacked), axis=0)
                    import rasterio.transform as rt_bc
                    vi = np.argwhere(valid_mask_bg)
                    xs_v, ys_v = rt_bc.xy(self.transform, vi[:,0], vi[:,1])
                    xs_v = np.array(xs_v); ys_v = np.array(ys_v)
                    # Gaussian kernel density sum at each background cell
                    bw = 0.5  # bandwidth in degrees (~55 km)
                    weights = np.zeros(len(xs_v))
                    for px, py in zip(pres_lons, pres_lats):
                        d2 = (xs_v - px)**2 + (ys_v - py)**2
                        weights += np.exp(-d2 / (2 * bw**2))
                    weights = weights + 1e-6  # avoid zero
                    bias_weights_bg = weights
                    self.progress_cb("Bias correction weights computed.", 46)
                except Exception as e_bias:
                    warnings.warn(f"Bias correction failed: {e_bias}. Sampling without bias correction.")
                    bias_weights_bg = None

            bg_lons, bg_lats = self._sample_background(
                self.n_background,
                min_dist_km  = self.mx_min_dist_km
                               if self.mx_bg_strategy == "disk" else 0.0,
                pres_lons    = pres_lons,
                pres_lats    = pres_lats,
                strategy     = self.mx_bg_strategy,
                bias_weights = bias_weights_bg,
            )
            bg_env = self._extract_env(bg_lons, bg_lats)
            # Drop rows with NaN
            valid_bg = bg_env.notna().all(axis=1).values
            self.background_X      = bg_env[valid_bg].reset_index(drop=True)
            self.background_coords = {
                "lon": bg_lons[valid_bg],
                "lat": bg_lats[valid_bg],
            }
            self.progress_cb(
                f"Background ready: {len(self.background_X)} points.", 46)
        except Exception as e:
            warnings.warn(f"MaxEnt background generation failed: {e}")
            self.background_X = None
            self.background_coords = None

        # ── Presence-only background (ENFA / Mahalanobis) ───────────────────
        try:
            if self.ponly_use_bg:
                self.progress_cb(
                    f"Generating presence-only background "
                    f"(n={self.ponly_n_bg}, strategy={self.ponly_strategy})…", 47)
                po_lons, po_lats = self._sample_background(
                    self.ponly_n_bg,
                    min_dist_km = self.ponly_min_dist_km
                        if self.ponly_strategy == "disk" else 0.0,
                    strategy    = "random",
                )
                po_env = self._extract_env(po_lons, po_lats)
                valid_po = po_env.notna().all(axis=1)
                self.background_ponly = po_env[valid_po].reset_index(drop=True)
                self.progress_cb(
                    f"Presence-only background ready: "
                    f"{len(self.background_ponly)} points.", 48)
            else:
                # Reuse PA pool as fallback
                self.background_ponly = None
        except Exception as e:
            warnings.warn(f"Presence-only background generation failed: {e}")
            self.background_ponly = None

        # var_names = continuous only (for VIF analysis)
        self.var_names = list(self.env_data.keys())

        # Categorical variables are always label-encoded (one column per raster)
        self.encoded_cat_names = list(self.cat_var_names)

        # Apply target encoding to all PA datasets if needed
        if self.cat_encoding == "target" and self.cat_var_names:
            self.progress_cb("Applying target encoding for categorical variables…", 47)
            new_pa = []
            for X_df, y_arr, coords in self.pa_datasets:
                X_enc = self._apply_target_encoding(X_df.copy(), y_arr)
                new_pa.append((X_enc, y_arr, coords))
            self.pa_datasets = new_pa

        # ── Automatic multicollinearity check ────────────────────────────
        self.progress_cb("Computing multicollinearity (VIF + correlation)…", 48)
        try:
            X_pool = pd.concat([ds[0] for ds in self.pa_datasets], ignore_index=True)
            y_pool = np.concatenate([ds[1] for ds in self.pa_datasets])
            X_clean = X_pool[self.var_names].dropna()
            y_clean  = np.array(y_pool[:len(X_clean)], dtype=float, copy=True)
            self.collinearity_df = variable_priority_ranking(
                X_clean.reset_index(drop=True), y_clean
            )
        except Exception as e:
            warnings.warn(f"Multicollinearity check failed: {e}")
            self.collinearity_df = None

        self.progress_cb("Data formatting complete.", 50)
        return self.pa_datasets


# ═══════════════════════════════════════════════════════════════════════════════
# 5. INDIVIDUAL MODELLING  (≈ BIOMOD_Modeling)
# ═══════════════════════════════════════════════════════════════════════════════

SUPPORTED_ALGORITHMS = ["GLM", "GBM", "RF", "BRT", "SVM", "ANN", "XGB", "LGB", "CAT", "GAM", "MAXENT", "ENFA", "MAHAL"]


def build_model(algo, algo_options=None):
    opts = algo_options or {}
    if algo == "GLM":
        degree = 2 if opts.get("type", "quadratic") == "quadratic" else 1
        return Pipeline([
            ("poly",  PolynomialFeatures(degree=degree, include_bias=False)),
            ("scale", StandardScaler()),
            ("clf",   LogisticRegression(max_iter=2000, solver="lbfgs", C=opts.get("C", 1.0)))
        ])
    elif algo == "GBM":
        return GradientBoostingClassifier(
            n_estimators=opts.get("n_estimators", 500),
            max_depth=opts.get("max_depth", 3),
            learning_rate=opts.get("learning_rate", 0.05))
    elif algo == "BRT":
        # Elith et al. (2008) Boosted Regression Trees for Ecological Modelling
        # defaults: tc=5 (max_depth), lr=0.01, bag.fraction=0.75 (subsample)
        # Reference: Elith, J., Leathwick, J.R., Hastie, T. (2008).
        #   A working guide to boosted regression trees.
        #   J. Animal Ecology 77(4):802-813.
        #   https://doi.org/10.1111/j.1365-2656.2008.01390.x
        return GradientBoostingClassifier(
            n_estimators    = opts.get("n_estimators", 1000),
            max_depth       = opts.get("max_depth", 5),        # tc=5 (Elith et al.)
            learning_rate   = opts.get("learning_rate", 0.01), # lr=0.01 (Elith et al.)
            subsample       = opts.get("subsample", 0.75),     # bag.fraction=0.75
            min_samples_leaf= opts.get("min_samples_leaf", 10))
    elif algo == "RF":
        # Breiman (2001) Random Forests. Machine Learning 45(1):5-32.
        # Default n_estimators=500: Oshiro et al. (2012) recommend
        # ≥128 trees; 500 provides stable OOB error in most SDM datasets.
        # max_features="sqrt" (sklearn default) = Breiman's recommended sqrt(p).
        return RandomForestClassifier(
            n_estimators    = opts.get("n_estimators", 500),
            max_depth       = opts.get("max_depth", None),
            min_samples_leaf= opts.get("min_samples_leaf", 1),
            n_jobs          = -1)
    elif algo == "SVM":
        return Pipeline([
            ("scaler", StandardScaler()),
            ("clf", SVC(C=opts.get("C", 1.0), kernel=opts.get("kernel", "rbf"),
                        gamma=opts.get("gamma", "scale"), probability=True))])
    elif algo == "ANN":
        hidden = opts.get("hidden_layer_sizes", (100, 50))
        if isinstance(hidden, str):
            hidden = tuple(int(x.strip()) for x in hidden.split(","))
        return Pipeline([
            ("scaler", StandardScaler()),
            ("clf", MLPClassifier(hidden_layer_sizes=hidden,
                                   activation=opts.get("activation", "relu"),
                                   max_iter=opts.get("max_iter", 2000),
                                   random_state=42))])
    elif algo == "XGB":
        if not HAS_XGB:
            raise ImportError("xgboost required. pip install xgboost")
        # use_label_encoder removed in XGBoost >= 2.0 — build kwargs dynamically
        xgb_kwargs = dict(
            n_estimators    = opts.get("n_estimators", 500),
            max_depth       = opts.get("max_depth", 6),
            learning_rate   = opts.get("learning_rate", 0.05),
            subsample       = opts.get("subsample", 0.8),
            colsample_bytree= opts.get("colsample_bytree", 0.8),
            min_child_weight= opts.get("min_child_weight", 1),
            gamma           = opts.get("gamma", 0),
            reg_alpha       = opts.get("reg_alpha", 0),
            reg_lambda      = opts.get("reg_lambda", 1),
            eval_metric     = "logloss",
            random_state    = 42,
            n_jobs          = -1,
            verbosity       = 0,
        )
        # Add use_label_encoder=False only for XGBoost < 2.0
        try:
            xgb_ver = tuple(int(x) for x in xgb.__version__.split(".")[:2])
            if xgb_ver < (2, 0):
                xgb_kwargs["use_label_encoder"] = False
        except Exception:
            pass
        return xgb.XGBClassifier(**xgb_kwargs)

    elif algo == "LGB":
        if not HAS_LGB:
            raise ImportError("lightgbm required. pip install lightgbm")
        return lgb.LGBMClassifier(
            n_estimators     = opts.get("n_estimators", 500),
            max_depth        = opts.get("max_depth", -1),     # -1 = unlimited
            learning_rate    = opts.get("learning_rate", 0.05),
            num_leaves       = opts.get("num_leaves", 31),
            subsample        = opts.get("subsample", 0.8),
            colsample_bytree = opts.get("colsample_bytree", 0.8),
            min_child_samples= opts.get("min_child_samples", 20),
            reg_alpha        = opts.get("reg_alpha", 0.0),
            reg_lambda       = opts.get("reg_lambda", 0.0),
            random_state     = 42,
            n_jobs           = -1,
            verbose          = -1,
            force_row_wise   = True,   # suppress threading warning
        )

    elif algo == "CAT":
        if not HAS_CAT:
            raise ImportError("catboost required. pip install catboost")
        return cb.CatBoostClassifier(
            iterations      = opts.get("iterations", 500),
            depth           = opts.get("depth", 6),
            learning_rate   = opts.get("learning_rate", 0.05),
            l2_leaf_reg     = opts.get("l2_leaf_reg", 3),
            border_count    = opts.get("border_count", 128),
            random_strength = opts.get("random_strength", 1),
            bagging_temperature=opts.get("bagging_temperature", 1),
            random_seed     = 42,
            verbose         = 0,
            allow_writing_files=False,
        )

    elif algo == "GAM":
        if not HAS_GAM:
            raise ImportError("pygam required. pip install pygam")
        return "GAM"
    elif algo == "MAXENT":
        if not HAS_MAXENT:
            raise ImportError("elapid required. pip install elapid")
        return "MAXENT"
    else:
        raise ValueError(f"Unknown algorithm: {algo}")


class SDMModeler:
    def __init__(self, pa_datasets, var_names,
                 algorithms=None, algo_options=None,
                 n_cv_runs=2, data_split=80, var_import_n=3,
                 maxent_background=None,
                 ponly_background=None,
                 cont_var_names=None,
                 threshold_method="max_tss",
                 progress_callback=None,
                 test_occurrence_csv=None,
                 formatter=None):
        self.pa_datasets        = pa_datasets
        self.var_names          = var_names
        self.cont_var_names     = cont_var_names or var_names
        self.algorithms         = algorithms or ["GLM", "RF"]
        self.algo_options       = algo_options or {}
        self.n_cv_runs          = n_cv_runs
        self.data_split         = data_split
        self.var_import_n       = var_import_n
        self.progress_cb        = progress_callback or (lambda m, p: None)
        self._maxent_background = maxent_background
        self._ponly_background  = ponly_background
        self.threshold_method   = threshold_method
        self._test_occurrence_csv = test_occurrence_csv
        self._formatter           = formatter
        self._ext_test_X          = None   # populated by _load_external_test()
        self._ext_test_y          = None
        self._ext_test_coords     = None

        self.fitted_models      = {}
        self.evaluation_scores  = {}
        self.variable_importance= {}
        self.tss_thresholds     = {}
        self.split_coords       = {}

    # ── ENFA ──────────────────────────────────────────────────────────────
    def _fit_enfa(self, X_tr, y_tr):
        """
        Ecological Niche Factor Analysis (ENFA) — presence-only algorithm.

        Algorithm (Hirzel et al. 2002):
          1. Compute global mean (μ_g) and covariance (Σ_g) from ALL training
             rows (presence + background/pseudo-absence).
          2. Compute species mean (μ_s) from PRESENCE rows only.
          3. Marginality vector m = Σ_g^{-1/2} (μ_s − μ_g)  (standardised
             deviation of the species' habitat from the global mean).
          4. Specialisation: eigenanalysis of the species covariance
             (Σ_g^{-1/2} Σ_s Σ_g^{-1/2}) restricted to the subspace
             orthogonal to m; first K eigenvalues capture specialisation.
          5. Habitat suitability score = HS(x) = exp(−0.5 · d_m² − 0.5 · d_s²)
             where d_m is the projection of x onto the marginality axis
             and d_s is the Mahalanobis distance in the specialisation space.

        For prediction we store:
          - marginality_vec  : unit vector along marginality axis
          - marginality_shift: μ_s − μ_g  (bias shift)
          - spec_vectors     : top K specialisation eigenvectors
          - spec_eigenvalues : corresponding eigenvalues
          - global_cov_sqrt_inv: Σ_g^{-1/2} for feature whitening
        """
        from sklearn.preprocessing import StandardScaler
        from sklearn.covariance import LedoitWolf

        pres_mask = y_tr == 1
        X_pres    = X_tr[pres_mask].astype(float)
        # Global statistics: use dedicated ponly background if available
        if (self._ponly_background is not None
                and len(self._ponly_background) > 0):
            cols = list(range(X_tr.shape[1]))
            # Map column indices to var_names for DataFrame lookup
            bg_cols = self.var_names[:X_tr.shape[1]]
            available = [c for c in bg_cols
                         if c in self._ponly_background.columns]
            if len(available) == X_tr.shape[1]:
                X_all = self._ponly_background[available].fillna(0).values.astype(float)
            else:
                X_all = X_tr.astype(float)
        else:
            X_all = X_tr.astype(float)

        if len(X_pres) < 2:
            raise ValueError("ENFA requires at least 2 presence records.")

        # Global statistics (all rows = presence + background)
        mu_g  = X_all.mean(axis=0)
        # Robust covariance via Ledoit-Wolf shrinkage
        lw_g  = LedoitWolf().fit(X_all)
        cov_g = lw_g.covariance_

        # Regularise to avoid singular matrix
        reg = 1e-6 * np.eye(cov_g.shape[0])
        cov_g_reg = cov_g + reg

        # Square root inverse of global covariance (for whitening)
        eigvals_g, eigvecs_g = np.linalg.eigh(cov_g_reg)
        eigvals_g = np.maximum(eigvals_g, 1e-10)
        cov_g_sqrt     = eigvecs_g @ np.diag(np.sqrt(eigvals_g))    @ eigvecs_g.T
        cov_g_sqrt_inv = eigvecs_g @ np.diag(1.0/np.sqrt(eigvals_g)) @ eigvecs_g.T

        # Species mean
        mu_s = X_pres.mean(axis=0)

        # Marginality vector (whitened)
        m_raw = cov_g_sqrt_inv @ (mu_s - mu_g)
        m_norm = np.linalg.norm(m_raw)
        if m_norm < 1e-12:
            m_raw = np.ones(len(mu_g)) / np.sqrt(len(mu_g))
            m_norm = 1.0
        marginality_unit = m_raw / m_norm   # unit vector

        # Specialisation: covariance of whitened presence data
        X_pres_w = (X_pres - mu_g) @ cov_g_sqrt_inv.T
        cov_s_w  = np.cov(X_pres_w.T) + reg

        # Project covariance onto subspace orthogonal to marginality axis
        m_u = marginality_unit.reshape(-1, 1)
        P   = np.eye(len(mu_g)) - m_u @ m_u.T  # projection matrix
        cov_s_proj = P @ cov_s_w @ P

        # Top K specialisation axes
        K = min(3, len(mu_g) - 1)
        eigvals_s, eigvecs_s = np.linalg.eigh(cov_s_proj)
        # Sort descending
        order = np.argsort(eigvals_s)[::-1]
        eigvals_s = eigvals_s[order[:K]]
        eigvecs_s = eigvecs_s[:, order[:K]]
        # Keep only positive eigenvalues
        pos = eigvals_s > 1e-8
        if pos.sum() == 0:
            eigvals_s = np.array([1.0])
            eigvecs_s = marginality_unit.reshape(-1, 1)
        else:
            eigvals_s = eigvals_s[pos]
            eigvecs_s = eigvecs_s[:, pos]

        return {
            "_type":            "ENFA",
            "mu_g":             mu_g,
            "cov_g_sqrt_inv":   cov_g_sqrt_inv,
            "marginality_unit": marginality_unit,
            "marginality_norm": float(m_norm),
            "mu_s_w":           (mu_s - mu_g) @ cov_g_sqrt_inv.T,
            "spec_vectors":     eigvecs_s,
            "spec_eigenvalues": eigvals_s,
        }

    def _predict_enfa(self, model, X):
        """
        Compute ENFA habitat suitability scores in [0, 1].

        HS(x) = exp(−0.5 · [(proj_m − μ_m)² + Σ_k (proj_k − μ_k)² / λ_k])

        where proj_m is the projection onto the marginality axis and
        proj_k are projections onto the top K specialisation axes.
        """
        X = np.asarray(X, dtype=float)
        mu_g       = model["mu_g"]
        S_inv      = model["cov_g_sqrt_inv"]
        m_unit     = model["marginality_unit"]
        mu_s_w     = model["mu_s_w"]
        spec_vecs  = model["spec_vectors"]
        spec_vals  = model["spec_eigenvalues"]

        # Whiten
        X_w = (X - mu_g) @ S_inv.T

        # Marginality distance
        proj_m  = X_w @ m_unit
        mu_m    = mu_s_w @ m_unit
        d_m_sq  = (proj_m - mu_m) ** 2

        # Specialisation distances
        d_s_sq  = np.zeros(len(X))
        for k in range(spec_vecs.shape[1]):
            proj_k = X_w @ spec_vecs[:, k]
            mu_k   = mu_s_w @ spec_vecs[:, k]
            lam_k  = max(spec_vals[k], 1e-8)
            d_s_sq += (proj_k - mu_k) ** 2 / lam_k

        scores = np.exp(-0.5 * (d_m_sq + d_s_sq))
        # Normalise to [0, 1]
        mn, mx = scores.min(), scores.max()
        if mx > mn:
            scores = (scores - mn) / (mx - mn)
        return scores

    # ── Mahalanobis distance ──────────────────────────────────────────────
    def _fit_mahal(self, X_tr, y_tr):
        """
        Mahalanobis Distance Niche Model — presence-only.

        Algorithm:
          1. Compute presence mean μ_s and covariance Σ_s from presence rows.
          2. Regularise Σ_s with Ledoit-Wolf shrinkage.
          3. At prediction: D²(x) = (x − μ_s)ᵀ Σ_s^{-1} (x − μ_s)
          4. Convert to probability:
             P(x) = exp(−0.5 · D²) — the multivariate Gaussian density
             evaluated at x under the species niche distribution.
          5. Normalise to [0, 1].

        References:
          Farber & Kadmon (2003). Diversity and Distributions 9:341-352.
          Etherington (2019). PeerJ 7:e6678.
        """
        from sklearn.covariance import LedoitWolf

        pres_mask = y_tr == 1
        X_pres    = X_tr[pres_mask].astype(float)

        if len(X_pres) < 2:
            raise ValueError("Mahalanobis requires at least 2 presence records.")

        mu_s = X_pres.mean(axis=0)

        # Robust covariance
        lw = LedoitWolf().fit(X_pres)
        cov_s = lw.covariance_ + 1e-6 * np.eye(X_pres.shape[1])

        cov_inv = np.linalg.inv(cov_s)

        return {
            "_type":   "MAHAL",
            "mu_s":    mu_s,
            "cov_inv": cov_inv,
        }

    def _predict_mahal(self, model, X):
        """
        Mahalanobis suitability score:  exp(−0.5 · D²(x))  normalised to [0, 1].
        """
        X       = np.asarray(X, dtype=float)
        mu_s    = model["mu_s"]
        cov_inv = model["cov_inv"]

        diff    = X - mu_s                              # (n, p)
        d2      = np.einsum("ni,ij,nj->n", diff, cov_inv, diff)  # D²
        scores  = np.exp(-0.5 * d2)

        mn, mx = scores.min(), scores.max()
        if mx > mn:
            scores = (scores - mn) / (mx - mn)
        return scores

    def _fit_gam(self, X_tr, y_tr):
        if not HAS_GAM:
            raise ImportError("pygam required. pip install pygam")
        n = X_tr.shape[1]
        terms = s(0)
        for i in range(1, n):
            terms += s(i)
        gam = LogisticGAM(terms)
        gam.fit(X_tr, y_tr)
        return gam

    def _fit_maxent(self, X_tr, y_tr, opts=None):
        """
        Fit MaxEnt via elapid.
        elapid >=0.6: train_test_split style — X is presence+background stacked,
                      y is 1 for presence, 0 for background.
        elapid <0.6:  fit(presence_df, background_df) style.
        We try both approaches automatically.
        """
        import pandas as pd
        try:
            import elapid as elapid_mod
        except ImportError:
            import sys
            raise RuntimeError(
                f"elapid is not installed.\n"
                f"Python executable: {sys.executable}\n"
                f"Install it with:\n"
                f"  pip install elapid\n"
                f"Then restart HABITUS.")
        opts = opts or {}
        cols = self.var_names

        pres_mask = y_tr == 1
        X_pres = X_tr[pres_mask]
        if len(X_pres) == 0:
            raise ValueError(
                "MaxEnt: no presence records in training split. "
                "Try increasing data split % or pseudo-absence repetitions.")

        # Background DataFrame — dedicated background preferred
        if (self._maxent_background is not None
                and len(self._maxent_background) > 0):
            X_bg_df = self._maxent_background[cols].dropna().reset_index(drop=True)
        else:
            X_bg = X_tr[~pres_mask]
            if len(X_bg) == 0:
                raise ValueError("MaxEnt: no background points available.")
            X_bg_df = pd.DataFrame(X_bg, columns=cols)

        X_pres_df = pd.DataFrame(X_pres, columns=cols)

        # Build model — try parameter sets from most to least specific
        # elapid API changed across versions; fall back gracefully
        feature_types = opts.get("feature_types", ["linear", "hinge", "product"])
        if isinstance(feature_types, str):
            feature_types = [x.strip() for x in feature_types.split(",") if x.strip()]
        beta = float(opts.get("beta", 1.0))
        n_hinge = int(opts.get("n_hinge", 50))
        use_lambdas = opts.get("use_lambdas", "best")

        model = None
        for kwargs in [
            dict(feature_types=feature_types,
                 regularization_multiplier=beta,
                 n_hinge_features=n_hinge,
                 use_lambdas=use_lambdas,
                 verbose=False),
            dict(feature_types=feature_types,
                 regularization_multiplier=beta,
                 n_hinge_features=n_hinge),
            dict(feature_types=feature_types,
                 regularization_multiplier=beta),
            dict(feature_types=feature_types),
            {},
        ]:
            try:
                model = elapid_mod.MaxentModel(**kwargs)
                break
            except TypeError:
                continue
        if model is None:
            raise RuntimeError(
                "Could not instantiate MaxentModel — check elapid version "
                "(pip install --upgrade elapid)")

        # Fit the model — try multiple API styles
        fitted = False
        # Style 1: fit(X_combined, y) — elapid >= 0.6
        try:
            y_fit = np.concatenate([
                np.ones(len(X_pres_df)),
                np.zeros(len(X_bg_df))
            ])
            X_fit = pd.concat([X_pres_df, X_bg_df], ignore_index=True)
            model.fit(X_fit, y_fit)
            fitted = True
        except (TypeError, ValueError, Exception):
            pass

        # Style 2: fit(presence_df, background_df) — older elapid
        if not fitted:
            try:
                model.fit(X_pres_df, X_bg_df)
                fitted = True
            except Exception:
                pass

        # Style 3: fit(presence_df, background_df, labels=...) — some versions
        if not fitted:
            try:
                model.fit(presence=X_pres_df, background=X_bg_df)
                fitted = True
            except Exception:
                pass

        if not fitted:
            raise RuntimeError(
                "MaxentModel.fit() failed with all known API styles. "
                "Try: pip install --upgrade elapid")

        return model

    def _predict_maxent(self, model, X_arr, chunk_size=50000):
        """
        Predict MaxEnt suitability in chunks to avoid MemoryError on large rasters.

        Parameters
        ----------
        chunk_size : int
            Rows per chunk (default 50 000 ≈ 45 MB at 119 float64 columns).
            Reduce if still hitting memory limits.
        """
        import pandas as pd
        n = len(X_arr)
        all_probs = np.empty(n, dtype=float)

        for start in range(0, n, chunk_size):
            end   = min(start + chunk_size, n)
            chunk = X_arr[start:end]
            X_df  = pd.DataFrame(chunk, columns=self.var_names)
            predicted = False
            for predict_fn in [
                lambda m, X: m.predict(X),
                lambda m, X: m.predict_proba(X)[:, 1],
                lambda m, X: m.predict_proba(X),
                lambda m, X: np.array(m.predict(X.values)),
            ]:
                try:
                    result = predict_fn(model, X_df)
                    p = np.array(result, dtype=float).ravel()
                    if len(p) == len(chunk):
                        predicted = True
                        break
                except Exception:
                    continue
            if not predicted:
                p = np.full(len(chunk), 0.5)
            all_probs[start:end] = np.array(p, dtype=float).ravel()

        all_probs = np.where(np.isfinite(all_probs), all_probs, 0.0)
        mn, mx = all_probs.min(), all_probs.max()
        if mx > mn:
            all_probs = (all_probs - mn) / (mx - mn)
        return all_probs

    def _predict(self, model, algo, X):
        if algo == "GAM":
            return model.predict_proba(X)
        if algo == "MAXENT":
            return self._predict_maxent(model, X)
        if algo == "ENFA":
            return self._predict_enfa(model, X)
        if algo == "MAHAL":
            return self._predict_mahal(model, X)
        return model.predict_proba(X)[:, 1]

    def _load_external_test(self):
        """Load and extract env features for the external test occurrence CSV."""
        fmt = self._formatter
        if fmt is None:
            raise ValueError("formatter required for external test CSV extraction.")
        import pandas as pd
        df = pd.read_csv(self._test_occurrence_csv)
        cols = list(df.columns)
        lon_col, lat_col = cols[1], cols[2]
        lons = df[lon_col].values.astype(float)
        lats = df[lat_col].values.astype(float)

        # Filter same way as training points
        lons, lats = fmt._filter_presence_points(lons, lats)
        env_df = fmt._extract_env(lons, lats)

        # Build X/y matching var_names
        X = env_df[self.var_names].values.astype(float)
        y = np.ones(len(X), dtype=int)   # all test points are presences

        valid = np.isfinite(X).all(axis=1)
        self._ext_test_X      = X[valid]
        self._ext_test_y      = y[valid]
        self._ext_test_coords = {"lon": lons[valid].tolist(),
                                 "lat": lats[valid].tolist()}
        self.progress_cb(
            f"External test set loaded: {len(self._ext_test_X)} valid presence points.", 5)

    def run(self):
        import time as _time
        _t_run = _time.perf_counter()

        if self._test_occurrence_csv:
            self._load_external_test()

        n_pa  = len(self.pa_datasets)
        total = len(self.algorithms) * n_pa * self.n_cv_runs
        step  = 0

        for pa_idx, (X_all, y_all, _) in enumerate(self.pa_datasets):
            X_arr = X_all[self.var_names].values.astype(float)
            y_arr = y_all.astype(int)

            # Drop rows with NaN (categorical rasters may have nodata pixels)
            valid_mask = np.isfinite(X_arr).all(axis=1)
            if not valid_mask.all():
                n_drop = int((~valid_mask).sum())
                self.progress_cb(f"  Dropping {n_drop} rows with NaN in PA{pa_idx+1}", 0)
                X_arr = X_arr[valid_mask]
                y_arr = y_arr[valid_mask]

            for algo in self.algorithms:
                _t_algo = _time.perf_counter()
                for cv_run in range(self.n_cv_runs):
                    step += 1
                    pct = 50 + int(40 * step / total)
                    key = (algo, f"PA{pa_idx+1}", f"RUN{cv_run+1}")
                    self.progress_cb(f"Fitting {algo} | PA{pa_idx+1} | RUN{cv_run+1}…", pct)

                    if self._ext_test_X is not None:
                        # External test set: train on ALL pa data, test on external points
                        # Combine pa training data (all) with external test presences for BG
                        X_tr, y_tr = X_arr, y_arr
                        X_te = np.vstack([
                            self._ext_test_X,
                            X_arr[y_arr == 0][:len(self._ext_test_X)]
                        ])
                        y_te = np.concatenate([
                            self._ext_test_y,
                            np.zeros(min(len(self._ext_test_X), (y_arr == 0).sum()), dtype=int)
                        ])
                        tr = np.arange(len(X_arr))
                        te = None   # not used for coord indexing below
                    else:
                        # Stratified split: presence and background split separately
                        # to guarantee data_split% of PRESENCES go to training
                        np.random.seed(cv_run * 100 + pa_idx)
                        pres_idx = np.where(y_arr == 1)[0]
                        bg_idx   = np.where(y_arr == 0)[0]
                        pres_idx = pres_idx[np.random.permutation(len(pres_idx))]
                        bg_idx   = bg_idx[np.random.permutation(len(bg_idx))]
                        n_pres_tr = max(1, int(len(pres_idx) * self.data_split / 100))
                        n_bg_tr   = int(len(bg_idx) * self.data_split / 100)
                        tr = np.concatenate([pres_idx[:n_pres_tr], bg_idx[:n_bg_tr]])
                        te = np.concatenate([pres_idx[n_pres_tr:], bg_idx[n_bg_tr:]])
                        X_tr, X_te = X_arr[tr], X_arr[te]
                        y_tr, y_te = y_arr[tr], y_arr[te]

                    # Presence-only algorithms need at least 1 presence in test set
                    # for evaluation (ROC/TSS/Boyce require both classes).
                    # If test set has no presences, move some from train to test.
                    if algo in ("MAXENT", "ENFA", "MAHAL") and y_te.sum() == 0:
                        pres_in_tr = np.where(y_tr == 1)[0]
                        if len(pres_in_tr) > 1:
                            # Move ~20% of training presences to test
                            n_move = max(1, len(pres_in_tr) // 5)
                            move_idx = pres_in_tr[:n_move]
                            # Rebuild tr/te
                            tr_list = list(tr); te_list = list(te)
                            for mi in sorted(move_idx, reverse=True):
                                te_list.append(tr_list[mi])
                                tr_list.pop(mi)
                            tr = np.array(tr_list); te = np.array(te_list)
                            X_tr, X_te = X_arr[tr], X_arr[te]
                            y_tr, y_te = y_arr[tr], y_arr[te]

                    # Store train/test coordinates from first CV run
                    pa_key = f"PA{pa_idx+1}"
                    if cv_run == 0 and pa_key not in self.split_coords:
                        if self._ext_test_X is not None and self._ext_test_coords:
                            coords = self.pa_datasets[pa_idx][2]
                            lons_tr = coords.get("lon", np.array([]))
                            lats_tr = coords.get("lat", np.array([]))
                            if len(lons_tr) > len(y_arr):
                                lons_tr = lons_tr[valid_mask]
                                lats_tr = lats_tr[valid_mask]
                            self.split_coords[pa_key] = {
                                "train": {
                                    "lon": lons_tr.tolist(),
                                    "lat": lats_tr.tolist(),
                                    "y":   y_arr.tolist(),
                                },
                                "test": {
                                    "lon": self._ext_test_coords["lon"],
                                    "lat": self._ext_test_coords["lat"],
                                    "y":   self._ext_test_y.tolist(),
                                },
                            }
                        elif te is not None:
                            coords = self.pa_datasets[pa_idx][2]
                            lons = coords.get("lon", np.array([]))
                            lats = coords.get("lat", np.array([]))
                            if len(lons) > len(y_arr):
                                lons = lons[valid_mask]
                                lats = lats[valid_mask]
                            n_coord = len(lons)
                            n = len(y_arr)
                            if n_coord == n:
                                self.split_coords[pa_key] = {
                                    "train": {
                                        "lon": lons[tr].tolist(),
                                        "lat": lats[tr].tolist(),
                                        "y":   y_arr[tr].tolist(),
                                    },
                                    "test": {
                                        "lon": lons[te].tolist(),
                                        "lat": lats[te].tolist(),
                                        "y":   y_arr[te].tolist(),
                                    },
                                }

                    try:
                        if algo == "GAM":
                            model = self._fit_gam(X_tr, y_tr)
                        elif algo == "MAXENT":
                            model = self._fit_maxent(X_tr, y_tr, self.algo_options.get("MAXENT", {}))
                        elif algo == "ENFA":
                            model = self._fit_enfa(X_tr, y_tr)
                        elif algo == "MAHAL":
                            model = self._fit_mahal(X_tr, y_tr)
                        else:
                            model = build_model(algo, self.algo_options.get(algo, {}))
                            model.fit(X_tr, y_tr)

                        probs = self._predict(model, algo, X_te)
                        scores = evaluate_all(y_te, probs)

                        self.fitted_models[key]     = model
                        self.evaluation_scores[key] = scores
                        self.tss_thresholds[key]    = scores["_thr"]

                        if self.var_import_n > 0:
                            imp_list = []
                            if algo in ("GAM",):
                                # GAM: use built-in coefficient magnitudes as proxy
                                pass  # no importance for GAM
                            elif algo in ("ENFA", "MAHAL"):
                                # Presence-only distance models: custom permutation
                                for _ in range(self.var_import_n):
                                    base_auc = compute_roc_auc(y_te, self._predict(model, algo, X_te))
                                    importances = []
                                    for vi in range(X_te.shape[1]):
                                        X_shuf = X_te.copy()
                                        np.random.shuffle(X_shuf[:, vi])
                                        try:
                                            shuf_probs = self._predict(model, algo, X_shuf)
                                            shuf_auc   = compute_roc_auc(y_te, shuf_probs)
                                            importances.append(base_auc - shuf_auc)
                                        except Exception:
                                            importances.append(0.0)
                                    imp_list.append(np.array(importances))
                            elif algo == "MAXENT":
                                # MaxEnt permutation importance:
                                # shuffle each variable and measure AUC drop
                                for _ in range(self.var_import_n):
                                    base_auc = compute_roc_auc(y_te, self._predict(model, algo, X_te))
                                    importances = []
                                    for vi in range(X_te.shape[1]):
                                        X_shuf = X_te.copy()
                                        np.random.shuffle(X_shuf[:, vi])
                                        try:
                                            shuf_probs = self._predict(model, algo, X_shuf)
                                            shuf_auc   = compute_roc_auc(y_te, shuf_probs)
                                            importances.append(base_auc - shuf_auc)
                                        except Exception:
                                            importances.append(0.0)
                                    imp_list.append(np.array(importances))
                            else:
                                for _ in range(self.var_import_n):
                                    pi = permutation_importance(model, X_te, y_te,
                                                                n_repeats=3, random_state=42,
                                                                scoring="roc_auc")
                                    imp_list.append(pi.importances_mean)
                            if imp_list:
                                result = np.mean(imp_list, axis=0)
                                # Güvenlik: 1-D array olduğundan emin ol
                                if np.ndim(result) == 0:
                                    result = np.zeros(len(self.var_names))
                                self.variable_importance[key] = np.asarray(result).ravel()
                            # imp_list boşsa (GAM vb.) kaydetme — grafik bu key'i atlar

                    except Exception as e:
                        import traceback
                        tb = traceback.format_exc()
                        warnings.warn(f"Model {key} FAILED: {type(e).__name__}: {e}\n{tb}")
                        self.progress_cb(f"FAILED {key}: {type(e).__name__}: {str(e)[:120]}", 0)
                        self.evaluation_scores[key] = {"ROC": np.nan, "TSS": np.nan, "Boyce": np.nan, "_thr": 0.5}

                _algo_elapsed = _time.perf_counter() - _t_algo
                self.progress_cb(
                    f"  ↳ {algo} PA{pa_idx+1} — {self.n_cv_runs} CV run(s) completed "
                    f"in {_algo_elapsed:.1f}s", 0)

        # Full models — trained on ALL data (used for projection)
        for pa_idx, (X_all, y_all, _) in enumerate(self.pa_datasets):
            X_arr = X_all[self.var_names].values.astype(float)
            y_arr = y_all.astype(int)

            # Drop rows with NaN
            valid_mask = np.isfinite(X_arr).all(axis=1)
            if not valid_mask.all():
                X_arr = X_arr[valid_mask]
                y_arr = y_arr[valid_mask]

            for algo in self.algorithms:
                key = (algo, f"PA{pa_idx+1}", "Full")
                _t_full = _time.perf_counter()
                self.progress_cb(f"Fitting full model {algo} PA{pa_idx+1}…",
                                 88 + pa_idx)
                try:
                    # ── Held-out evaluation split ────────────────────────────
                    np.random.seed(42 + pa_idx)
                    n_full   = len(y_arr)
                    n_tr_eval = int(n_full * self.data_split / 100)
                    idx_eval  = np.random.permutation(n_full)
                    tr_ev, te_ev = idx_eval[:n_tr_eval], idx_eval[n_tr_eval:]
                    X_tr_ev, X_te_ev = X_arr[tr_ev], X_arr[te_ev]
                    y_tr_ev, y_te_ev = y_arr[tr_ev], y_arr[te_ev]

                    # Presence-only: ensure test set has at least 1 presence
                    if algo in ("MAXENT", "ENFA", "MAHAL") and y_te_ev.sum() == 0:
                        pres_tr = np.where(y_tr_ev == 1)[0]
                        if len(pres_tr) > 1:
                            n_move = max(1, len(pres_tr) // 5)
                            mv = pres_tr[:n_move]
                            tr_list = list(tr_ev); te_list = list(te_ev)
                            for mi in sorted(mv, reverse=True):
                                te_list.append(tr_list[mi]); tr_list.pop(mi)
                            tr_ev = np.array(tr_list); te_ev = np.array(te_list)
                            X_tr_ev, X_te_ev = X_arr[tr_ev], X_arr[te_ev]
                            y_tr_ev, y_te_ev = y_arr[tr_ev], y_arr[te_ev]

                    # Step 1: fit on training split → evaluate on held-out
                    if algo == "GAM":
                        eval_model = self._fit_gam(X_tr_ev, y_tr_ev)
                    elif algo == "MAXENT":
                        eval_model = self._fit_maxent(X_tr_ev, y_tr_ev,
                                                      self.algo_options.get("MAXENT", {}))
                    elif algo == "ENFA":
                        eval_model = self._fit_enfa(X_tr_ev, y_tr_ev)
                    elif algo == "MAHAL":
                        eval_model = self._fit_mahal(X_tr_ev, y_tr_ev)
                    else:
                        eval_model = build_model(algo, self.algo_options.get(algo, {}))
                        eval_model.fit(X_tr_ev, y_tr_ev)

                    probs_eval = self._predict(eval_model, algo, X_te_ev)
                    scores     = evaluate_all(y_te_ev, probs_eval,
                                             threshold_method=self.threshold_method)

                    # Step 2: refit on ALL data for projection
                    if algo == "GAM":
                        model = self._fit_gam(X_arr, y_arr)
                    elif algo == "MAXENT":
                        model = self._fit_maxent(X_arr, y_arr,
                                                 self.algo_options.get("MAXENT", {}))
                    elif algo == "ENFA":
                        model = self._fit_enfa(X_arr, y_arr)
                    elif algo == "MAHAL":
                        model = self._fit_mahal(X_arr, y_arr)
                    else:
                        model = build_model(algo, self.algo_options.get(algo, {}))
                        model.fit(X_arr, y_arr)

                    self.fitted_models[key]     = model
                    self.evaluation_scores[key] = scores
                    self.tss_thresholds[key]    = scores["_thr"]
                    _full_elapsed = _time.perf_counter() - _t_full
                    self.progress_cb(
                        f"Full model {algo} PA{pa_idx+1} ready — "
                        f"ROC={scores['ROC']:.3f}  TSS={scores['TSS']:.3f}  "
                        f"({_full_elapsed:.1f}s)", 89)
                except Exception as e:
                    # Log clearly so user can see which model failed and why
                    err_msg = f"Full model {key} FAILED: {type(e).__name__}: {e}"
                    warnings.warn(err_msg)
                    self.progress_cb(err_msg[:120], 89)
                    # Store NaN scores so it appears in evaluation table
                    self.evaluation_scores[key] = {
                        "ROC": np.nan, "TSS": np.nan, "Boyce": np.nan, "_thr": 0.5}

        _total_elapsed = _time.perf_counter() - _t_run
        m, s = divmod(int(_total_elapsed), 60)
        self.progress_cb(
            f"Individual modelling complete.  Total time: "
            f"{m}m {s:02d}s  ({_total_elapsed:.1f}s)", 90)

    def get_evaluations_df(self):
        rows = []
        for (algo, pa, run), sc in self.evaluation_scores.items():
            rows.append({"Algorithm": algo, "PA_set": pa, "CV_run": run,
                         "ROC": sc.get("ROC", np.nan),
                         "TSS": sc.get("TSS", np.nan),
                         "Boyce": sc.get("Boyce", np.nan)})
        return pd.DataFrame(rows)

    def get_variable_importance_df(self):
        rows = []
        for (algo, pa, run), imp in self.variable_importance.items():
            try:
                imp_arr = np.asarray(imp).ravel()
                if imp_arr.ndim != 1 or len(imp_arr) == 0:
                    continue
                for vi, vname in zip(imp_arr, self.var_names):
                    rows.append({"Algorithm": algo, "PA_set": pa, "CV_run": run,
                                 "Variable": vname, "Importance": float(vi)})
            except Exception:
                continue
        return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ENSEMBLE  (≈ BIOMOD_EnsembleModeling)
# ═══════════════════════════════════════════════════════════════════════════════

class EnsembleModeler:
    def __init__(self, modeler, eval_metric="TSS",
                 quality_threshold=0.7,
                 methods=("committee_averaging", "weighted_mean"),
                 progress_callback=None):
        self.modeler           = modeler
        self.eval_metric       = eval_metric
        self.quality_threshold = quality_threshold
        self.methods           = methods
        self.progress_cb       = progress_callback or (lambda m, p: None)
        self.selected_keys     = []
        self.weights           = {}
        self.ensemble_scores   = {}

    def _filter_models(self):
        selected, weights = [], {}
        for key, sc in self.modeler.evaluation_scores.items():
            val = sc.get(self.eval_metric, 0)
            if not np.isnan(val) and val >= self.quality_threshold:
                selected.append(key)
                weights[key] = val
        self.selected_keys = selected
        total = sum(weights.values()) or 1
        self.weights = {k: v / total for k, v in weights.items()}
        return selected

    def predict_ensemble(self, X_arr):
        keys = self._filter_models()
        if not keys:
            return None
        preds, w_vec = [], []
        for key in keys:
            model = self.modeler.fitted_models.get(key)
            if model is None:
                continue
            try:
                p = self.modeler._predict(model, key[0], X_arr)
                preds.append(p); w_vec.append(self.weights[key])
            except Exception:
                pass
        if not preds:
            return None
        preds_arr = np.stack(preds, axis=0)
        w_arr     = np.array(w_vec)
        binaries  = []
        for i, key in enumerate(keys[:len(preds)]):
            thr = self.modeler.tss_thresholds.get(key, 0.5)
            binaries.append((preds_arr[i] >= thr).astype(float))
        ca    = np.stack(binaries, axis=0).mean(axis=0)
        wmean = (preds_arr * w_arr[:, None]).sum(axis=0)
        return {"ca": ca, "wmean": wmean}

    def evaluate(self, X_arr, y_arr):
        result = self.predict_ensemble(X_arr)
        if result is None:
            return {}
        scores = {}
        for name, probs in result.items():
            scores[name] = evaluate_all(y_arr, probs)
        self.ensemble_scores = scores
        return scores


# ═══════════════════════════════════════════════════════════════════════════════
# 7. PROJECTION  (≈ BIOMOD_Projection)
# ═══════════════════════════════════════════════════════════════════════════════

class Projector:
    def __init__(self, modeler, ensemble_modeler,
                 progress_callback=None, formatter=None):
        self.modeler          = modeler
        self.ensemble_modeler = ensemble_modeler
        self.progress_cb      = progress_callback or (lambda m, p: None)
        self.formatter        = formatter   # for categorical raster encoding

    def _read_env_stack(self, raster_paths, var_names,
                         cat_raster_paths=None, formatter=None):
        """
        Read continuous rasters (positional) and categorical rasters (by stem name).
        Returns: arrays dict {varname: 2D array}, meta, transform, shape

        Continuous rasters: positional mapping (i-th file = i-th var_name).
        Categorical rasters: loaded by stem, then one-hot/label encoded
                             using the class definitions from formatter.
        """
        import rasterio as rio
        if len(raster_paths) != len(var_names):
            raise ValueError(
                f"Raster count mismatch: got {len(raster_paths)} continuous files "
                f"but model has {len(var_names)} continuous variables "
                f"({', '.join(var_names)}). "
                f"Add exactly {len(var_names)} rasters in the same order."
            )
        from rasterio.enums import Resampling as _Resamp
        arrays, meta, transform, shape = {}, None, None, None
        ref_h, ref_w = None, None   # reference dimensions (from first raster)

        # Continuous
        for vname, rpath in zip(var_names, raster_paths):
            with rio.open(rpath) as src:
                if ref_h is None:
                    # First raster sets the reference grid
                    band = src.read(1).astype(float)
                    meta = src.meta.copy()
                    transform = src.transform
                    ref_h, ref_w = band.shape
                    shape = band.shape
                else:
                    # Resample subsequent rasters to match reference dims
                    if src.height != ref_h or src.width != ref_w:
                        band = src.read(1, out_shape=(ref_h, ref_w),
                                        resampling=_Resamp.bilinear).astype(float)
                    else:
                        band = src.read(1).astype(float)
                nd = src.nodata
                if nd is not None:
                    band[band == nd] = np.nan
                arrays[vname] = band

        # Categorical
        if cat_raster_paths and formatter is not None:
            enc = getattr(formatter, "cat_encoding", "one-hot")
            for rpath in cat_raster_paths:
                vname = _sanitize_varname(Path(rpath).stem)
                with rio.open(rpath) as src:
                    if ref_h is not None and (src.height != ref_h or src.width != ref_w):
                        band_int = src.read(1, out_shape=(ref_h, ref_w),
                                            resampling=_Resamp.nearest).astype(np.int32)
                    else:
                        band_int = src.read(1).astype(np.int32)
                    nd = src.nodata
                    if nd is not None:
                        band_int[band_int == int(nd)] = -9999
                classes = formatter.cat_classes.get(vname, [])
                if enc == "label":
                    b = band_int.astype(float)
                    b[band_int == -9999] = np.nan
                    arrays[vname] = b
                elif enc == "target":
                    # Use mean of training target per class
                    b = np.full(band_int.shape, np.nan, dtype=float)
                    if hasattr(formatter, "_target_enc_map"):
                        cls_map = formatter._target_enc_map.get(vname, {})
                        global_m = formatter._target_enc_map.get("__global__", 0.5)
                        for cls in classes:
                            b[band_int == cls] = cls_map.get(cls, global_m)
                    arrays[vname] = b
                else:  # label (default for projection too)
                    b = band_int.astype(float)
                    b[band_int == -9999] = np.nan
                    arrays[vname] = b

        return arrays, meta, transform, shape

    def project(self, raster_paths, proj_name, output_dir,
                binary_method="TSS", progress_cb=None,
                selected_algorithms=None):
        """
        Project models onto raster stack.

        Parameters
        ----------
        raster_paths         : list of raster file paths (same order/count as var_names)
        proj_name            : scenario label (e.g. 'current', '2050_SSP245')
        output_dir           : directory to save GeoTIFFs
        selected_algorithms  : list of algorithm names to project (e.g. ['RF', 'MAXENT']).
                               None = all fitted algorithms.
        """
        if progress_cb:
            self.progress_cb = progress_cb
        import rasterio as rio
        import time as _time
        _t_proj = _time.perf_counter()

        # Species name prefix for output filenames
        _sp = getattr(self.formatter, "species_name", "") if self.formatter else ""
        _sp = (_sp.replace(' ', '_').strip('_') + "_") if _sp else ""

        # cont_var_names = continuous only (rasters needed)
        # var_names      = cont + encoded categorical (all model features)
        all_var_names  = self.modeler.var_names
        # Derive continuous vars by removing categorical names
        cat_names_set = set()
        if self.formatter:
            cat_names_set = set(getattr(self.formatter, "cat_var_names", []))
            cat_names_set |= set(getattr(self.formatter, "encoded_cat_names", []))
        stored_cont = getattr(self.modeler, "cont_var_names", None)
        if stored_cont and len(stored_cont) < len(all_var_names):
            cont_var_names = stored_cont
        else:
            cont_var_names = [v for v in all_var_names if v not in cat_names_set]

        self.progress_cb(f"Loading env stack for '{proj_name}'…", 5)

        # Rasters loaded for continuous vars (positional) +
        # categorical vars encoded via formatter
        cat_raster_paths = []
        if self.formatter and hasattr(self.formatter, "cat_rasters"):
            cat_raster_paths = list(self.formatter.cat_rasters)

        arrays, meta, transform, shape = self._read_env_stack(
            raster_paths, cont_var_names,
            cat_raster_paths=cat_raster_paths,
            formatter=self.formatter)
        nrows, ncols = shape

        # Build feature matrix for ALL model variables
        feat_arrays = []
        for v in all_var_names:
            if v in arrays:
                feat_arrays.append(arrays[v].ravel())
            else:
                feat_arrays.append(np.zeros(nrows * ncols, dtype=float))
        X_flat = np.stack(feat_arrays, axis=1)

        # valid_mask: ALL columns (continuous + categorical) must be finite
        valid_mask = np.all(np.isfinite(X_flat), axis=1)
        X_valid = X_flat[valid_mask]

        # ── Output raster metadata ───────────────────────────────────────
        out_meta = meta.copy()

        # Always write as float32 with nodata=-9999 (values in [0,1])
        out_meta.update({
            "driver":  "GTiff",
            "dtype":   "float32",
            "nodata":  -9999.0,
            "count":   1,
        })

        # Assign WGS84 CRS if source raster is already geographic (lat/lon).
        # If source is projected (UTM etc.) we keep original CRS so
        # transform stays consistent — user can reproject in QGIS if needed.
        try:
            from rasterio.crs import CRS as RioCRS
            src_crs = meta.get("crs")
            if src_crs is None or (hasattr(src_crs, "is_geographic") and src_crs.is_geographic):
                out_meta["crs"] = RioCRS.from_epsg(4326)
            # else keep original projected CRS
        except Exception:
            pass

        os.makedirs(output_dir, exist_ok=True)
        output_files = {}
        threshold_log = {}   # {key_name: threshold_value} for reporting

        # Filter to selected algorithms only
        algo_filter = set(selected_algorithms) if selected_algorithms else None

        # Only project "Full" models (trained on all data) — skip CV runs for projection
        # This matches biomod2 behaviour: projections use the full-data models
        proj_keys = [
            key for key in self.modeler.fitted_models
            if key[2] == "Full"
            and (algo_filter is None or key[0] in algo_filter)
        ]

        if not proj_keys:
            raise ValueError(
                "No Full models found for selected algorithms. "
                "Check that modelling completed successfully."
            )

        self.progress_cb(
            f"Projecting {len(proj_keys)} models "
            f"({', '.join(sorted(set(k[0] for k in proj_keys)))})…", 10
        )

        total = len(proj_keys)
        for i, key in enumerate(proj_keys):
            algo, pa, run = key
            model = self.modeler.fitted_models[key]
            pct = 10 + int(55 * i / max(total, 1))
            self.progress_cb(f"Projecting {algo} {pa}…", pct)
            try:
                self.progress_cb(
                    f"  X_valid shape: {X_valid.shape}, "
                    f"model vars: {len(self.modeler.var_names)}", pct)
                probs_v  = self.modeler._predict(model, algo, X_valid)

                # ── Normalise to strict [0, 1] ───────────────────────────
                probs_v = np.array(probs_v, dtype=float)
                probs_v = np.where(np.isfinite(probs_v), probs_v, 0.0)
                mn, mx = probs_v.min(), probs_v.max()
                if mx > mn:
                    probs_v = (probs_v - mn) / (mx - mn)
                probs_v = np.clip(probs_v, 0.0, 1.0)

                prob_map = np.full(nrows * ncols, -9999.0, dtype=np.float32)
                prob_map[valid_mask] = probs_v.astype(np.float32)
                prob_map = prob_map.reshape(nrows, ncols)

                fname = f"{_sp}{proj_name}_{algo}_{pa}_prob.tif"
                fpath = os.path.join(output_dir, fname)
                with rio.open(fpath, "w", **out_meta) as dst:
                    dst.write(prob_map, 1)
                    # Write statistics so QGIS reads correct 0-1 range
                    dst.update_tags(1, STATISTICS_MINIMUM="0",
                                       STATISTICS_MAXIMUM="1",
                                       STATISTICS_MEAN="0.5")
                output_files[f"{algo}_{pa}_prob"] = fpath
                # Copy QML sidecar so QGIS auto-loads the style
                _copy_suitability_qml(fpath)

                # ── Binary map using stored optimal threshold ────────────
                thr = self.modeler.tss_thresholds.get(key, 0.5)
                bin_map = np.where(prob_map >= thr, 1.0, 0.0).astype(np.float32)
                bin_map[prob_map == -9999.0] = -9999.0
                fname_b = f"{_sp}{proj_name}_{algo}_{pa}_bin.tif"
                fpath_b = os.path.join(output_dir, fname_b)
                with rio.open(fpath_b, "w", **out_meta) as dst:
                    dst.write(bin_map, 1)
                output_files[f"{algo}_{pa}_bin"] = fpath_b
                threshold_log[f"{algo}_{pa}"] = round(float(thr), 4)

            except Exception as e:
                import traceback as _tb
                tb_str = _tb.format_exc()
                err = f"Projection {key} FAILED: {type(e).__name__}: {e}"
                warnings.warn(err + "\n" + tb_str)
                self.progress_cb(err[:180], pct)
                # Log first meaningful line of traceback
                for line in tb_str.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("Traceback") and "File" not in line:
                        self.progress_cb(f"  → {line[:160]}", pct)
                        break

        # Ensemble projection
        self.progress_cb("Projecting ensemble…", 70)
        try:
            ens = self.ensemble_modeler.predict_ensemble(X_valid)
            if ens:
                for ens_name, probs_v in ens.items():
                    prob_map = np.full(nrows * ncols, -9999.0, dtype=np.float32)
                    prob_map[valid_mask] = probs_v.astype(np.float32)
                    prob_map = prob_map.reshape(nrows, ncols)

                    # Normalise ensemble predictions to [0, 1]
                    probs_v_ens = np.where(np.isfinite(probs_v), probs_v, 0.0)
                    mn_e, mx_e  = probs_v_ens.min(), probs_v_ens.max()
                    if mx_e > mn_e:
                        probs_v_ens = (probs_v_ens - mn_e) / (mx_e - mn_e)
                    probs_v_ens = np.clip(probs_v_ens, 0.0, 1.0)

                    prob_map = np.full(nrows * ncols, -9999.0, dtype=np.float32)
                    prob_map[valid_mask] = probs_v_ens.astype(np.float32)
                    prob_map = prob_map.reshape(nrows, ncols)

                    fname = f"{_sp}{proj_name}_EM{ens_name}_prob.tif"
                    fpath = os.path.join(output_dir, fname)
                    with rio.open(fpath, "w", **out_meta) as dst:
                        dst.write(prob_map, 1)
                        dst.update_tags(1, STATISTICS_MINIMUM="0",
                                           STATISTICS_MAXIMUM="1",
                                           STATISTICS_MEAN="0.5")
                    output_files[f"EM{ens_name}_prob"] = fpath
                    _copy_suitability_qml(fpath)

                    # Ensemble binary — use mean TSS threshold of selected models
                    ens_thrs = [self.modeler.tss_thresholds.get(k, 0.5)
                                for k in (self.ensemble_modeler.selected_keys or [])]
                    ens_thr = float(np.mean(ens_thrs)) if ens_thrs else 0.5
                    bin_map = np.where(prob_map >= ens_thr, 1.0, 0.0).astype(np.float32)
                    bin_map[prob_map == -9999.0] = -9999.0
                    fname_b = f"{_sp}{proj_name}_EM{ens_name}_bin.tif"
                    fpath_b = os.path.join(output_dir, fname_b)
                    with rio.open(fpath_b, "w", **out_meta) as dst:
                        dst.write(bin_map, 1)
                    output_files[f"EM{ens_name}_bin"] = fpath_b
                    threshold_log[f"EM{ens_name}"] = round(ens_thr, 4)
        except Exception as e:
            import traceback as _tb
            err = f"Ensemble projection FAILED: {type(e).__name__}: {e}"
            warnings.warn(err)
            self.progress_cb(err[:200], 75)
            self.progress_cb(_tb.format_exc()[-300:], 75)

        # Log thresholds used
        if threshold_log:
            thr_str = "  |  ".join(f"{k}={v}" for k,v in threshold_log.items())
            self.progress_cb(f"Thresholds used: {thr_str}", 100)

        _proj_elapsed = _time.perf_counter() - _t_proj
        _pm, _ps = divmod(int(_proj_elapsed), 60)
        self.progress_cb(
            f"Projection complete (WGS84, values 0–1).  "
            f"Time: {_pm}m {_ps:02d}s  ({_proj_elapsed:.1f}s)", 100)
        return output_files


# ═══════════════════════════════════════════════════════════════════════════════
# 8. SPECIES RANGE CHANGE  (≈ BIOMOD_RangeSize)
# ═══════════════════════════════════════════════════════════════════════════════

class RangeChangeAnalyzer:
    @staticmethod
    def compute(bin_current_path, bin_future_path, output_path):
        import rasterio as rio
        from rasterio.enums import Resampling
        with rio.open(bin_current_path) as src:
            curr = src.read(1).astype(float); nd = src.nodata or -9999.0; meta = src.meta.copy()
            curr_h, curr_w = curr.shape
        with rio.open(bin_future_path) as src:
            # Resample future to match current dimensions if they differ
            if src.height != curr_h or src.width != curr_w:
                fut = src.read(1, out_shape=(curr_h, curr_w),
                               resampling=Resampling.nearest).astype(float)
            else:
                fut = src.read(1).astype(float)
        valid = (curr != nd) & (fut != nd)
        result = np.full_like(curr, nd, dtype=np.float32)
        lost = valid & (curr == 1) & (fut == 0)
        gained = valid & (curr == 0) & (fut == 1)
        pres = valid & (curr == 1) & (fut == 1)
        absent = valid & (curr == 0) & (fut == 0)
        result[lost] = -2; result[absent] = 0; result[pres] = 1; result[gained] = 2
        meta.update({"dtype": "float32", "nodata": nd, "driver": "GTiff"})
        with rio.open(output_path, "w", **meta) as dst:
            dst.write(result, 1)
        tc = int((curr[valid] == 1).sum()); tf = int((fut[valid] == 1).sum())
        stats = {"Lost": int(lost.sum()), "Stable_Absent": int(absent.sum()),
                 "Stable_Present": int(pres.sum()), "Gained": int(gained.sum()),
                 "Total_Current": tc, "Total_Future": tf,
                 "Pct_Lost":   round(100 * lost.sum() / max(tc, 1), 2),
                 "Pct_Gained": round(100 * gained.sum() / max(tc, 1), 2),
                 "Net_Change": round(100 * (tf - tc) / max(tc, 1), 2)}
        return stats, output_path


# ═══════════════════════════════════════════════════════════════════════════════
# 9. RESPONSE CURVES
# ═══════════════════════════════════════════════════════════════════════════════

def compute_response_curves(modeler, pa_datasets, var_names,
                             n_points=100, method="marginal"):
    """
    Compute 1-D response curves per variable × algorithm.

    Parameters
    ----------
    method : str
        "marginal" (default) — vary one variable while holding all others
            at their median value.  Fast, interpretable, shows the marginal
            effect of each predictor (Elith et al. 2005; biomod2 style).

        "partial" — Partial Dependence Plot (PDP, Friedman 2001).
            For each focal variable, vary it across its range while cycling
            through the ACTUAL observed values of all other variables, then
            average.  Captures average marginal effect accounting for the
            joint distribution of predictors — more statistically rigorous
            than the median-hold approach but ~N× slower.

        "ice" — Individual Conditional Expectation (Goldstein et al. 2015).
            Like PDP but returns per-sample curves (mean + SD across samples).
            Reveals interaction effects hidden by PDP averaging.

    References
    ----------
    Elith et al. (2005) Ecological Modelling 190:490-509.
    Friedman (2001) Ann. Stat. 29(5):1189-1232.  [PDP]
    Goldstein et al. (2015) J. Comput. Graph. Stat. 24(1):44-65.  [ICE]
    """
    import pandas as pd

    # Use only continuous variables for response curves
    # (categorical encoded columns are not meaningful to vary continuously)
    cont_vars = getattr(modeler, "cont_var_names", None) or var_names
    # Intersect with available columns
    X_pool  = pd.concat([ds[0] for ds in pa_datasets], ignore_index=True)
    cont_vars = [v for v in cont_vars if v in X_pool.columns]
    if not cont_vars:
        return {}

    X_all   = X_pool[cont_vars].dropna()
    medians = X_all.median()

    # For prediction we need ALL model columns (cont + cat encoded)
    all_vars  = modeler.var_names  # full feature list used by model
    # Build a median row for all vars (cat encoded cols will be their median/mode)
    X_pool_all = X_pool[all_vars].dropna() if all(v in X_pool.columns for v in all_vars) else X_pool[cont_vars].dropna()
    medians_all = X_pool_all.median() if all(v in X_pool.columns for v in all_vars) else medians

    def _predict_safe(model, algo, X_df):
        """Predict using the right method for each algorithm type."""
        X_np = X_df.values.astype(float)
        if algo == "MAXENT":
            return modeler._predict_maxent(model, X_np)
        elif algo == "ENFA":
            return modeler._predict_enfa(model, X_np)
        elif algo == "MAHAL":
            return modeler._predict_mahal(model, X_np)
        elif algo == "GAM":
            return model.predict_proba(X_np)
        else:
            return model.predict_proba(X_np)[:, 1]

    curves = {}
    for algo in modeler.algorithms:
        curves[algo] = {}
        for vname in cont_vars:
            x_range = np.linspace(
                X_all[vname].quantile(0.05),
                X_all[vname].quantile(0.95),
                n_points)

            preds_per = []
            for key, model in modeler.fitted_models.items():
                if key[0] != algo:
                    continue

                try:
                    if method == "partial":
                        X_bg = X_pool_all.sample(
                            min(500, len(X_pool_all)), random_state=42
                        ).reset_index(drop=True)
                        pdp_vals = []
                        for xv in x_range:
                            X_tmp = X_bg.copy()
                            X_tmp[vname] = xv
                            p_tmp = _predict_safe(model, algo, X_tmp)
                            pdp_vals.append(float(p_tmp.mean()))
                        preds_per.append(np.array(pdp_vals))

                    elif method == "ice":
                        X_bg = X_pool_all.sample(
                            min(200, len(X_pool_all)), random_state=42
                        ).reset_index(drop=True)
                        ice_mat = []
                        for xv in x_range:
                            X_tmp = X_bg.copy()
                            X_tmp[vname] = xv
                            p_tmp = _predict_safe(model, algo, X_tmp)
                            ice_mat.append(p_tmp)
                        ice_arr = np.stack(ice_mat, axis=1)
                        preds_per.append(ice_arr.mean(axis=0))

                    else:  # marginal (default)
                        # Build baseline row using all model columns
                        X_resp = pd.DataFrame(
                            np.tile(medians_all.values, (n_points, 1)),
                            columns=list(medians_all.index))
                        X_resp[vname] = x_range
                        # Ensure column order matches model training order
                        X_resp = X_resp.reindex(columns=all_vars, fill_value=0.0)
                        p = _predict_safe(model, algo, X_resp)
                        preds_per.append(p)

                except Exception:
                    continue

            if preds_per:
                arr = np.stack(preds_per, axis=0)
                curves[algo][vname] = (x_range, arr.mean(axis=0), arr.std(axis=0))

    # ── Categorical variable bar charts ─────────────────────────────────
    # For each categorical column: show mean predicted suitability per class
    cat_vars = [v for v in (modeler.var_names or [])
                if v not in cont_vars and v in X_pool.columns]

    for algo in modeler.algorithms:
        for cat_var in cat_vars:
            class_vals = sorted(X_pool[cat_var].dropna().unique())
            if len(class_vals) < 2 or len(class_vals) > 60:
                continue   # skip constant or over-cardinality columns

            preds_per_class = {cls: [] for cls in class_vals}
            for key, model in modeler.fitted_models.items():
                if key[0] != algo:
                    continue
                try:
                    for cls in class_vals:
                        # Build a single row with all vars at median, cat=cls
                        row = medians_all.copy()
                        row[cat_var] = cls
                        X_row = pd.DataFrame([row], columns=list(medians_all.index))
                        X_row = X_row.reindex(columns=all_vars, fill_value=0.0)
                        p = _predict_safe(model, algo, X_row)
                        preds_per_class[cls].append(float(p.mean()))
                except Exception:
                    continue

            class_means = [float(np.mean(preds_per_class[c]))
                           if preds_per_class[c] else 0.0
                           for c in class_vals]
            class_stds  = [float(np.std(preds_per_class[c]))
                           if preds_per_class[c] else 0.0
                           for c in class_vals]
            if any(v > 0 for v in class_means):
                # Store as special "categorical" entry: x=class labels, y=means, sd=stds
                curves[algo][f"_cat_{cat_var}"] = (
                    np.array(class_vals, dtype=float),
                    np.array(class_means),
                    np.array(class_stds),
                )

    return curves
