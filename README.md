# HABITUS v1.0.0

**Habitat Analysis and Biodiversity Integrated Toolkit for Unified Species Distribution Modelling (SDM)**

[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE.txt)
[![Python](https://img.shields.io/badge/python-3.11%2B-yellow)](https://www.python.org)

---

## Overview

HABITUS is a free, open-source standalone desktop application for Species Distribution Modelling (SDM). It implements **13 algorithms** within an **eight-step guided workflow** — from raw occurrence data through variable selection, model training, future climate projection, range-change analysis, accuracy assessment, and automated scientific report generation — without requiring R, QGIS, or command-line tools.

All analyses are performed within a single graphical user interface. The application runs on **Windows, macOS and Linux** and requires no programming expertise.

---

## Features

### Modelling
- **13 SDM Algorithms** — GLM, GBM, BRT, RF, SVM, ANN, XGBoost, LightGBM, CatBoost, GAM, MaxEnt, ENFA, Mahalanobis Distance
- **Stratified Train/Test Split** — Presence and background points split independently for balanced evaluation sets
- **Pseudo-Absence Generation** — Random, disk exclusion, and Surface Range Envelope (SRE) strategies with independent settings for ML, MaxEnt and presence-only algorithms
- **Presence-Only Support** — MaxEnt, ENFA, and Mahalanobis Distance (no pseudo-absences required)
- **Ensemble Modelling** — TSS-weighted mean (EMwmean) and Committee Averaging (EMca)
- **Multi-Scenario Projection** — Current and unlimited future climate scenarios (CMIP6 / WorldClim / CHELSA); categorical variables reused automatically
- **Range Change Analysis** — Lost / Gained / Stable habitat with area statistics; auto-resamples mismatched raster dimensions

### Variable Analysis
- **VIF + Correlation** — Interactive Variance Inflation Factor and Pearson/Spearman correlation with visual heatmaps; variables with no high-correlation pair are auto-selected as safe
- **Advanced Analysis** — Condition Number (Belsley et al. 1980), Principal Component Analysis (PCA), LASSO (L1) regularisation with cross-validated alpha, Ridge (L2) regularisation

### Evaluation & Validation
- **Comprehensive Evaluation** — ROC-AUC, TSS, Continuous Boyce Index, permutation-based variable importance, response curves (marginal, PDP, ICE)
- **Individual Figure Export** — Per-algorithm ROC curves (`roc_curves/`), per-variable response curves (`response_curves/`), per-algorithm Boyce detail — all at 300 DPI
- **Five Optimal Threshold Methods** — max_TSS, max_Kappa, Sensitivity=Specificity, P10, min ROC distance
- **Validation Tab** — Binary mode (direct 0/1 comparison for external reference maps like EUFORGEN) and Continuous mode (reclassification with custom thresholds); auto-resamples mismatched dimensions
- **Ensemble Metrics** — EMwmean and EMca ROC-AUC, TSS and Boyce Index computed from probability rasters + held-out test data, included in evaluation_scores.csv

### Scientific Report (Tab ⑧)
- **10-Section HTML Report** — Automatically generated Q1-level scientific report covering summary, variable selection, methods, model parameters, evaluation results, current distribution maps, future projections, range change, validation, and session log
- **Embedded Figures** — User-exported map PNGs and all evaluation charts embedded directly in the report
- **Scientific Interpretations** — Per-metric textual interpretation (AUC, TSS, Boyce Index, Kappa) with literature-based thresholds
- **Geographic Aspect Ratio** — All map renders corrected with cosine-latitude scaling for undistorted display
- **One-Click Export** — Generates a self-contained HTML file with all figures base64-encoded

### User Interface
- **Embedded Map Viewer** — Eight literature-accepted colourmaps, train/test point overlays, layer switcher; geographic aspect ratio correction applied to all viewers (Distribution, Future, Range Change); smart save: `{species}_{layer}.png` default filename
- **Arial Font Standard** — Consistent Arial across all UI, plots, HTML help and exports
- **Screenshot Capture** — Camera icon button (Ctrl+Shift+S) saves the current window at 300 DPI
- **Auto Analysis Folder** — CSV selection creates `Documents/HABITUS/{species}_{timestamp}/` automatically; correctly resets for each new species analysis
- **Performance Logging** — Per-algorithm timing written to a timestamped `.log` file

### Distribution & Updates
- **Auto Update Check** — Notifies users when a new release is available on GitHub
- **Hot-Patch Update** — Apply code updates without reinstalling; `patches/` folder overrides frozen bytecode
- **Cross-Platform** — Windows installer (Inno Setup), macOS `.app` / `.dmg` and Linux AppImage / tar.gz built by GitHub Actions

---

## Workflow

```
1  Data         →  Load occurrence CSV + environmental rasters
2  Variables    →  VIF + correlation analysis, variable selection
    (optional)  →  Advanced: Condition Number, PCA, LASSO, Ridge
3  Models       →  Train 13 algorithms, ensemble, current distribution map
4  Future       →  Project onto future climate scenarios
5  Range Change →  Compare current vs future habitat extent
6  Evaluation   →  ROC, TSS, Boyce, response curves, variable importance
7  Validation   →  Accuracy assessment (Binary or Continuous mode)
8  Report       →  10-section HTML scientific report
```

---

## Installation

All installers are attached to the [v1.0.0 release](https://github.com/anonymised-2026/habitus/releases/tag/v1.0.0). Pick the section for your operating system.

### Windows — Installer (.exe)

**Requirements:** Windows 10 or 11 (64-bit).

1. Download `HABITUS_Setup_v1.0.0_Windows_x64.exe` from the release page.
2. Double-click the installer.
3. **First-run SmartScreen warning:** click **"More info"** → **"Run anyway"** (the binary is unsigned during peer review).
4. Follow the wizard (Next → Next → Install).
5. Launch **HABITUS** from the Start Menu or Desktop shortcut.

**Verify:** the main window opens with eight tabs (Data → … → Report).

### macOS — Disk image (.dmg)

**Requirements:** macOS 11 (Big Sur) or later, **Apple Silicon (arm64)**. Intel Mac users should build from source — see below.

1. Download `HABITUS_Setup_v1.0.0_macOS.dmg` from the release page.
2. Double-click the .dmg to mount it.
3. Drag **HABITUS.app** onto the **Applications** shortcut. Eject the disk image.
4. **First launch — bypass Gatekeeper (required once):**
   - In `/Applications`, **right-click** (or Control-click) **HABITUS.app**.
   - Choose **Open** from the menu.
   - In the warning dialog, click **Open** again.

   If no "Open" button is offered, run once in Terminal:
   ```bash
   xattr -dr com.apple.quarantine /Applications/HABITUS.app
   ```
   Then repeat the right-click → Open steps.

5. From the second launch onward, normal double-click works.

**Verify:** the main window opens with eight tabs.

### Linux — AppImage or tar.gz

**Requirements:** Ubuntu 20.04+ / Debian 11+ / Fedora 36+ (64-bit).

**Option A — AppImage (portable, recommended):**
```bash
chmod +x HABITUS_v1.0.0_x86_64.AppImage
./HABITUS_v1.0.0_x86_64.AppImage
```

**Option B — tar.gz archive:**
```bash
tar -xzf HABITUS_Setup_v1.0.0_Linux_x64.tar.gz
cd HABITUS
./HABITUS
```

**Verify:** the main window opens with eight tabs.

If the AppImage refuses to start, install FUSE:
```bash
sudo apt install libfuse2          # Debian / Ubuntu
sudo dnf install fuse-libs         # Fedora
```

### Run from source

```bash
git clone https://github.com/anonymised-2026/habitus.git
cd habitus
pip install PyQt6 matplotlib rasterio numpy pandas scipy scikit-learn pyproj
pip install xgboost lightgbm catboost pygam elapid   # optional algorithms
python main.py
```

#### macOS — Run from source

```bash
git clone https://github.com/anonymised-2026/habitus.git
cd habitus
pip install PyQt6 matplotlib rasterio numpy pandas scipy scikit-learn pyproj
python main.py
```

**Apple Silicon (M1/M2/M3) note:** `rasterio` wheels on PyPI may fail on arm64 due to GDAL binary mismatches. If the install errors on `rasterio`, install it from conda-forge first:

```bash
conda create -n habitus python=3.11
conda activate habitus
conda install -c conda-forge rasterio gdal
pip install PyQt6 matplotlib numpy pandas scipy scikit-learn pyproj
python main.py
```

### Build locally

| Platform | Script |
|----------|--------|
| Windows  | `pyinstaller habitus.spec --clean -y` then `ISCC habitus_setup.iss` |
| macOS    | `./build_mac.sh` |
| Linux    | `./build_linux.sh` |

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| **macOS:** "HABITUS is damaged and cannot be opened" | `xattr -dr com.apple.quarantine /Applications/HABITUS.app`, then open again |
| **macOS:** Double-click does nothing the first time | Use **right-click → Open** (Step 4 of the macOS section); only required once |
| **macOS source build:** `ModuleNotFoundError: No module named 'habitus'` | Pull the latest `main` (fixed in commit `3ce6f99`); the script now reads `version.py` directly |
| **Windows:** SmartScreen blocks the installer | Click **More info → Run anyway** (the binary is unsigned during peer review) |
| **Linux:** AppImage exits immediately | `sudo apt install libfuse2` (or `fuse-libs` on Fedora) |
| **All platforms:** `pip install rasterio` fails | Use conda-forge: `conda install -c conda-forge rasterio gdal` |
| **Anywhere else** | Open an issue on GitHub with the OS, Python version, and the full error message |

---

## Sample Data

Download **habitus_sample.zip** (~43 MB) from the release page to test HABITUS with a complete dataset:

| Component | Description |
|-----------|-------------|
| **Species** | *Pinus brutia* (Turkish Pine) — 108 occurrence records |
| **Continuous variables** | 19 bioclimatic (bio 1-19), Elevation |
| **Categorical variables** | Aspect, Slope, NDVI |
| **Validation** | EUFORGEN *Pinus brutia* reference distribution (binary raster) |
| **Resolution** | 2.5 arc-minute |
| **Climate model** | CNRM-ESM2-1 |
| **Scenarios** | SSP1-2.6, SSP2-4.5, SSP3-7.0, SSP5-8.5 |
| **Periods** | 2021-2040, 2041-2060, 2061-2080, 2081-2100 |

### First-run quick test

After installation, the fastest way to confirm a working setup is to run HABITUS against this dataset:

1. Download `habitus_sample.zip` from the [v1.0.0 release](https://github.com/anonymised-2026/habitus/releases/tag/v1.0.0) (~43 MB) and unzip it anywhere.
2. Launch HABITUS.
3. **Tab 1 — Data:** load the unzipped occurrence CSV and the environmental rasters folder.
4. **Tab 2 — Variables:** run VIF + correlation analysis.
5. **Tab 3 — Models:** train (≈ 5–15 minutes on a typical laptop).
6. **Tab 8 — Report:** export the 10-section HTML report.

A complete walk-through is provided in `HABITUS_MANUAL_EN.md` (also attached to the release).

---

## Algorithm Reference

| Code | Algorithm | Library | Paradigm |
|------|-----------|---------|----------|
| GLM | Generalised Linear Model | scikit-learn | PA |
| GBM | Gradient Boosting Machine | scikit-learn | PA |
| BRT | Boosted Regression Trees | scikit-learn | PA |
| RF | Random Forest | scikit-learn | PA |
| SVM | Support Vector Machine | scikit-learn | PA |
| ANN | Neural Network (MLP) | scikit-learn | PA |
| XGB | XGBoost | xgboost | PA |
| LGB | LightGBM | lightgbm | PA |
| CAT | CatBoost | catboost | PA |
| GAM | Generalised Additive Model | pygam | PA |
| MAXENT | Maximum Entropy | elapid | PO |
| ENFA | Ecological Niche Factor Analysis | NumPy | PO |
| MAHAL | Mahalanobis Distance | scikit-learn | PO |

**PA** = presence-absence · **PO** = presence-only

---

## Evaluation Metrics

| Metric | Range | Acceptable | Good | Reference |
|--------|-------|-----------|------|-----------|
| ROC-AUC | 0.5-1.0 | > 0.7 | > 0.8 | Fielding & Bell (1997) |
| TSS | -1 to +1 | > 0.4 | > 0.6 | Allouche et al. (2006) |
| Boyce Index | -1 to +1 | > 0.3 | > 0.5 | Hirzel et al. (2006) |
| Cohen's Kappa | -1 to +1 | > 0.4 | > 0.6 | Cohen (1960) |

---

## Multicollinearity Diagnostics

| Diagnostic | Purpose | Reference |
|------------|---------|-----------|
| **Condition Number** | Single-number multicollinearity severity | Belsley et al. (1980) |
| **PCA** | Variable clustering + non-redundant subset | Jolliffe (2002) |
| **LASSO (L1)** | Embedded variable selection via regularisation | Tibshirani (1996) |
| **Ridge (L2)** | Coefficient shrinkage under collinearity | Hoerl & Kennard (1970) |

---

## Output Files

| File / folder | Description |
|--------------|-------------|
| `current/` | Current probability + binary maps per algorithm + ensemble |
| `<scenario>/` | Future projection maps |
| `figures/` | Evaluation plots (ROC, scores, importance, response, Boyce) |
| `figures/roc_curves/` | Individual ROC curves per algorithm |
| `figures/response_curves/` | Individual response curves: `response_{ALGO}_{VAR}.png` |
| `csv/evaluation_scores.csv` | ROC, TSS, Boyce per algorithm + EMwmean/EMca |
| `csv/classification_thresholds.csv` | Five-method thresholds per algorithm |
| `csv/high_correlation_pairs.csv` | Correlated variable pairs |
| `csv/variable_priority_ranking.csv` | VIF, AUC, priority score |
| `validation/` | Reclassified reference/validation rasters |
| `advanced_analysis/` | PCA, LASSO, Ridge plots + CSVs |
| `*.log` | Timestamped log with per-algorithm timing |
| `*_report.html` | Self-contained 10-section scientific HTML report |

---

## Citation

```
[Authors removed for peer review] (2026). HABITUS: Habitat Analysis and Biodiversity
Integrated Toolkit for Unified Species Distribution Modelling. Ecological
Perspective, [Technical Report]. [DOI removed for peer review]
```

---

## Development Note

AI-assisted coding tools were used during software development to support code implementation and optimisation. The conceptual framework, algorithm design, and validation were fully developed and verified by the developers.

---

## Scientific References

- Allouche O. et al. (2006) *J. Applied Ecology* 43:1223-1232
- Barbet-Massin M. et al. (2012) *Methods Ecol. Evol.* 3:327-338
- Belsley D.A. et al. (1980) *Regression Diagnostics*. Wiley.
- Breiman L. (2001) *Machine Learning* 45:5-32
- Chen T. & Guestrin C. (2016) *KDD 2016*, 785-794
- Dormann C.F. et al. (2013) *Ecography* 36:27-46
- Elith J. et al. (2008) *J. Animal Ecology* 77:802-813
- Fielding A.H. & Bell J.F. (1997) *Environmental Conservation* 24:38-49
- Hirzel A.H. et al. (2006) *Ecological Modelling* 199:142-152
- Hoerl A.E. & Kennard R.W. (1970) *Technometrics* 12:55-67
- Ke G. et al. (2017) *NeurIPS 2017*, 3146-3154
- Liu C. et al. (2005) *Ecography* 28:385-393
- O'Brien R.M. (2007) *Quality & Quantity* 41:673-690
- Pearson R.G. et al. (2007) *J. Biogeography* 34:102-117
- Phillips S.J. et al. (2006) *Ecological Modelling* 190:231-259
- Prokhorenkova L. et al. (2018) *NeurIPS 2018*, 6638-6648
- Tibshirani R. (1996) *J. Roy. Stat. Soc. B* 58:267-288
- Zurell D. et al. (2020) *Ecography* 43:1261-1277

---

## License

MIT License — see [LICENSE.txt](LICENSE.txt) for details.

---

## Developers

[Authors removed for peer review]

---
