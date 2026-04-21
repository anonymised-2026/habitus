# -*- coding: utf-8 -*-
"""
Tab - Help & User Guide (English only)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextBrowser, QPushButton, QLabel
)
from PyQt6.QtCore import Qt


# ── Shared CSS ─────────────────────────────────────────────────────────────────
_CSS = """
<style>
  body   { background:#f5faf7; color:#1c3328; font-family:'Arial',sans-serif; font-size:13px; margin:0; padding:0; }
  h1     { color:#1d5235; font-size:20px; margin:0 0 4px 0; padding:16px 20px 0 20px; }
  h2     { color:#1d5235; font-size:15px; margin:20px 20px 6px 20px; border-bottom:1px solid #b8d4c4; padding-bottom:4px; }
  h3     { color:#2a6a48; font-size:13px; margin:12px 20px 4px 20px; }
  p,li   { margin:4px 20px; line-height:1.6; color:#1c3328; }
  ul,ol  { padding-left:36px; margin:4px 20px; }
  .box   { background:#ffffff; border:1px solid #c4ddd0; border-radius:6px; padding:10px 14px; margin:8px 20px; }
  .tip   { background:#eef7f2; border-left:4px solid #3a8c60; padding:8px 14px; margin:8px 20px; border-radius:0 6px 6px 0; color:#1d5235; }
  .warn  { background:#fdf6e8; border-left:4px solid #d4820a; padding:8px 14px; margin:8px 20px; border-radius:0 6px 6px 0; color:#5c3a00; }
  .step  { background:#ffffff; border:1px solid #3a8c60; border-radius:6px; padding:10px 14px; margin:6px 20px; }
  .badge { display:inline-block; background:#3a8c60; color:#ffffff; border-radius:12px; padding:1px 10px; font-size:12px; font-weight:bold; }
  table  { width:calc(100% - 40px); margin:8px 20px; border-collapse:collapse; }
  th     { background:#d4ead9; color:#1d5235; padding:6px 10px; text-align:left; border:1px solid #b8d4c4; }
  td     { padding:5px 10px; border:1px solid #c4ddd0; color:#1c3328; }
  tr:nth-child(even) td { background:#eef7f2; }
  .flow  { background:#f0faf4; border:1px solid #b8d4c4; border-radius:6px; padding:14px 20px; margin:8px 20px; font-family:'Arial',sans-serif; font-size:12px; color:#1d5235; line-height:2; }
  code   { background:#e8f5ed; color:#1a5235; padding:1px 6px; border-radius:3px; font-size:12px; border:1px solid #c4ddd0; }
  hr     { border:none; border-top:1px solid #c4ddd0; margin:12px 20px; }
  a      { color:#3a8c60; text-decoration:none; }
  a:hover{ text-decoration:underline; }
</style>
"""

# ══════════════════════════════════════════════════════════════════════════════
# ENGLISH PAGES
# ══════════════════════════════════════════════════════════════════════════════

EN_OVERVIEW = _CSS + """
<h1>HABITUS - User Guide</h1>
<p style="padding:0 20px; color:#74c69d;">
Habitat Analysis &amp; Biodiversity Integrated Toolkit for Unified Species Distribution Modelling
</p>

<h2>What is HABITUS?</h2>
<div class="box">
<p>HABITUS is a standalone desktop application designed for modelling the potential distribution
of species. It combines 13 different machine learning algorithms in a single interface to produce
habitat suitability maps and generate publication-ready scientific reports.</p>
<p>No R or QGIS installation required - runs out of the box.</p>
</div>

<h2>Typical Workflow</h2>
<div class="flow">
1 Data &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;-&gt;&nbsp; Load CSV + Rasters, generate pseudo-absences<br>
&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
2 Variables &nbsp;-&gt;&nbsp; VIF analysis, correlation matrix, variable selection<br>
&nbsp;&nbsp;&nbsp;&nbsp;(optional) 2b Advanced -&gt; Condition Number, PCA, LASSO, Ridge<br>
&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
3 Models &nbsp;&nbsp;&nbsp;&nbsp;-&gt;&nbsp; Select algorithms, run models, view current distribution map<br>
&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
4 Future &nbsp;&nbsp;&nbsp;&nbsp;-&gt;&nbsp; Project onto future climate scenarios (SSP245, RCP85...)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
5 Range Change -&gt; Compare current vs. future distribution (gained / lost area)<br>
&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
6 Evaluation &nbsp;-&gt;&nbsp; ROC curve, variable importance, response curves, Boyce index<br>
&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
7 Validation &nbsp;-&gt;&nbsp; Accuracy assessment between maps or against field data<br>
&nbsp;&nbsp;&nbsp;&nbsp;&darr;<br>
8 Report &nbsp;&nbsp;&nbsp;&nbsp;-&gt;&nbsp; Generate 10-section Q1-level scientific HTML report
</div>

<h2>Supported Algorithms</h2>
<table>
<tr><th>Category</th><th>Algorithm</th><th>Requirement</th></tr>
<tr><td>ML (Presence-Absence)</td><td>GLM, GBM, BRT, RF, SVM, ANN</td><td>scikit-learn (built-in)</td></tr>
<tr><td>Boosting</td><td>XGBoost, LightGBM, CatBoost</td><td>pip install xgboost / lightgbm / catboost</td></tr>
<tr><td>Additive</td><td>GAM</td><td>pip install pygam</td></tr>
<tr><td>Presence-Only</td><td>MaxEnt, ENFA, Mahalanobis</td><td>pip install elapid (for MaxEnt)</td></tr>
</table>

<h2>Quick Start</h2>
<ol>
<li>Prepare a <b>CSV file</b> with species occurrence records (species name, longitude, latitude columns)</li>
<li>Prepare your <b>bioclimatic raster files</b> (.tif format recommended)</li>
<li>Load files from the <b>① Data</b> tab — an output folder is created automatically</li>
<li>Follow the tabs in order</li>
<li>Use <b>⑧ Report</b> to generate a publication-ready HTML report when all steps are complete</li>
</ol>

<div class="tip">
<b>Tip:</b> Each tab is locked until the previous step is completed. Work through them in order.
</div>

<div class="tip">
<b>New Analysis:</b> Click the <b>New Analysis</b> button at the top to clear all data and start fresh for a new species. Each new analysis creates a separate output folder automatically.
</div>
"""

EN_DATA = _CSS + """
<h1>1 Data - Loading Input Data</h1>

<h2>Step 1 - Species Records (CSV)</h2>
<div class="step">
<p><span class="badge">1</span> Click <b>Browse...</b> and select your CSV file.</p>
<p>The CSV must contain at least three columns:</p>
</div>
<table>
<tr><th>Column</th><th>Default Name</th><th>Description</th></tr>
<tr><td>Longitude</td><td><code>long</code></td><td>Decimal degrees (WGS84)</td></tr>
<tr><td>Latitude</td><td><code>lat</code></td><td>Decimal degrees (WGS84)</td></tr>
<tr><td>Presence</td><td><code>presence</code></td><td>1 = Present, 0 = Absent (optional)</td></tr>
</table>
<div class="tip">If your column names differ, update the <b>Longitude column</b> and <b>Latitude column</b> fields accordingly.</div>

<h2>Step 2 - Environmental Rasters</h2>
<div class="step">
<p><span class="badge">2</span> Under the <b>Continuous Rasters</b> tab, click <b>Add Continuous Rasters...</b> to add bioclimatic variables (.tif).</p>
<ul>
<li>Supported formats: <code>.tif</code>, <code>.tiff</code>, <code>.asc</code>, <code>.img</code>, <code>.nc</code></li>
<li>File name = variable name (e.g. <code>bio_1.tif</code> &rarr; <code>bio_1</code>)</li>
<li>All rasters must share the same CRS and resolution</li>
</ul>
</div>

<div class="step">
<p><span class="badge">3</span> If you have categorical variables (land cover, soil type), add them from the <b>Categorical Rasters</b> tab.</p>
</div>

<h2>Step 3 - Background &amp; Pseudo-Absence Settings</h2>
<table>
<tr><th>Tab</th><th>For which algorithms</th><th>Recommended setting</th></tr>
<tr><td>ML Models</td><td>GLM, RF, GBM, SVM, ANN, BRT, GAM</td><td>2-4 repeats, 1000-5000 points</td></tr>
<tr><td>MaxEnt</td><td>MaxEnt</td><td>10,000 background points</td></tr>
<tr><td>ENFA / Mahalanobis</td><td>ENFA, Mahalanobis</td><td>5000 background points</td></tr>
</table>

<h2>Step 4 - Output Directory</h2>
<div class="step">
<p><span class="badge">4</span> Select the folder where all outputs will be saved.</p>
</div>

<div class="step">
<p><span class="badge">5</span> Click <b>Load Data</b>. When the process completes, the Variables tab becomes active.</p>
</div>

<div class="warn"><b>Warning:</b> All rasters must be in the same coordinate reference system (CRS). Mismatched CRS will cause errors.</div>
"""

EN_VIF = _CSS + """
<h1>2 Variables - Variable Selection</h1>

<h2>What are VIF and Correlation Analysis?</h2>
<div class="box">
<p><b>VIF (Variance Inflation Factor)</b> - Measures multicollinearity among predictors.
Variables with high VIF (&gt;10) destabilise the model.</p>
<p><b>Correlation Analysis</b> - Identifies variables that are very similar to each other (|r| &gt; 0.8).
It is recommended to remove one variable from each highly correlated pair.</p>
</div>

<h2>Step 1 - Configure Settings</h2>
<div class="step">
<p><span class="badge">1</span> Set the <b>Correlation threshold</b> (default: 0.8).</p>
<p><span class="badge">2</span> Choose <b>Correlation method</b>: Pearson (linear) or Spearman (rank-based).</p>
<p><span class="badge">3</span> Click <b>Compute</b>.</p>
</div>

<h2>Step 2 - Interpret Results</h2>
<p><b>Left panel:</b> Correlated pairs above the threshold are listed. From each pair, remove the one with <b>lower AUC</b> or <b>higher VIF</b>.</p>
<p><b>Right panel:</b> Variable checklist - tick/untick to include or exclude variables.</p>

<h2>Colour Codes</h2>
<table>
<tr><th>Colour</th><th>Meaning</th></tr>
<tr><td style="color:#52b788">Green</td><td>Low VIF - safe to use</td></tr>
<tr><td style="color:#f6ad55">Yellow</td><td>Moderate VIF (5-10) - use with caution</td></tr>
<tr><td style="color:#fc8181">Red</td><td>High VIF (&gt;10) - consider removing</td></tr>
</table>

<h2>Step 3 - Confirm</h2>
<div class="step">
<p><span class="badge">4</span> When satisfied with your variable selection, click <b>Confirm Selected Variables</b>. The Models tab becomes active.</p>
</div>

<div class="tip"><b>Tip:</b> The "Recommended" button automatically selects variables with high AUC and low VIF - a good starting point.</div>
"""

EN_MODELS = _CSS + """
<h1>3 Models - Model Training &amp; Current Distribution Map</h1>

<h2>Step 1 - Algorithm Selection</h2>
<div class="step">
<p><span class="badge">1</span> In the <b>Algorithm Settings</b> tab, check the algorithms you want to run.</p>
</div>
<table>
<tr><th>Algorithm</th><th>Advantage</th><th>Disadvantage</th></tr>
<tr><td>GLM</td><td>Fast, interpretable</td><td>Assumes linear relationships</td></tr>
<tr><td>RF</td><td>Robust, resistant to overfitting</td><td>May need larger datasets</td></tr>
<tr><td>GBM / BRT</td><td>High accuracy</td><td>Slow, requires parameter tuning</td></tr>
<tr><td>MaxEnt</td><td>Works with few records, ecologically interpretable</td><td>Requires elapid installation</td></tr>
<tr><td>ENFA</td><td>Works with presence-only data</td><td>Harder to interpret</td></tr>
<tr><td>XGBoost / LightGBM / CatBoost</td><td>State-of-the-art accuracy</td><td>Need &ge;100 records; prone to overfitting</td></tr>
</table>

<h2>Minimum Sample Size Guidelines</h2>
<div class="box">
<p>The following thresholds are based on Wisz et al. (2008), Hernandez et al. (2006), and van Proosdij et al. (2016).
These are <b>presence record</b> counts, not total rows in the CSV.</p>
</div>
<table>
<tr><th>Algorithm</th><th>Minimum</th><th>Recommended</th><th>Ideal</th></tr>
<tr><td>MaxEnt</td><td>10–15</td><td>30–50</td><td>100+</td></tr>
<tr><td>ENFA / Mahalanobis</td><td>15–30</td><td>50–100</td><td>200+</td></tr>
<tr><td>GLM</td><td>30–50</td><td>80–100</td><td>150+</td></tr>
<tr><td>GAM</td><td>50–80</td><td>100–150</td><td>200+</td></tr>
<tr><td>SVM / BRT</td><td>50</td><td>100–200</td><td>300+</td></tr>
<tr><td>RF / GBM / ANN</td><td>50–80</td><td>150–200</td><td>500+</td></tr>
<tr><td>XGBoost / LightGBM / CatBoost</td><td>100</td><td>200–300</td><td>500+</td></tr>
</table>
<div class="tip"><b>Rule of thumb:</b> With fewer than 30 records, restrict to MaxEnt, ENFA, Mahalanobis, and GLM.
With 30–100 records, GAM, BRT, SVM, and RF are viable. Gradient boosting algorithms require &ge;100 records.</div>

<h2>Step 2 - Training Settings</h2>
<div class="step">
<p><span class="badge">2</span> <b>Cross-validation runs</b>: 2–5 recommended. More runs = more reliable but slower.</p>
<p><span class="badge">3</span> <b>Data split</b>: 80% training / 20% test. Presence and background are split <b>independently</b> to ensure balanced test sets even with few records.</p>
<p><span class="badge">4</span> <b>Ensemble method</b>: Weighted Mean (TSS-weighted, recommended) or Committee Averaging.</p>
</div>

<h2>Step 3 - Run the Models</h2>
<div class="step">
<p><span class="badge">5</span> Click <b>Run Models</b>. Processing time depends on the number of algorithms and data size.</p>
</div>

<h2>Performance Metrics</h2>
<table>
<tr><th>Metric</th><th>Random</th><th>Good</th><th>Excellent</th><th>Reference</th></tr>
<tr><td>ROC-AUC</td><td>0.5</td><td>&gt;0.7</td><td>&gt;0.9</td><td>Fielding &amp; Bell (1997)</td></tr>
<tr><td>TSS</td><td>0.0</td><td>&gt;0.4</td><td>&gt;0.7</td><td>Allouche et al. (2006)</td></tr>
<tr><td>Boyce Index</td><td>~0</td><td>&gt;0.5</td><td>&gt;0.8</td><td>Hirzel et al. (2006)</td></tr>
<tr><td>Cohen's Kappa</td><td>0.0</td><td>&gt;0.4</td><td>&gt;0.6</td><td>Cohen (1960)</td></tr>
</table>

<h2>Step 4 - Current Distribution Map</h2>
<div class="step">
<p><span class="badge">6</span> When modelling is complete, switch to the <b>Current Distribution Map</b> sub-tab. The ensemble map loads automatically with geographically corrected aspect ratio.</p>
<p>Use <b>Save</b> from the toolbar to export the map as PNG — these saved files are included automatically in the Report (Tab ⑧).</p>
</div>

<div class="tip">You can zoom and pan in the map viewer using the toolbar at the top. Eight colourmaps are available from the dropdown.</div>
"""

EN_FUTURE = _CSS + """
<h1>4 Future Scenarios - Future Projection</h1>

<h2>What is this Tab For?</h2>
<div class="box">
<p>Apply trained models to <b>future climate scenarios</b> (SSP245, RCP85, etc.) to predict
where the species could occur in the future.</p>
<p>Categorical variables (land cover, aspect, slope, etc.) are reused from the current
dataset automatically - do not include them in future rasters.</p>
</div>

<h2>Step 1 - Scenario Name</h2>
<div class="step">
<p><span class="badge">1</span> Enter a meaningful name: e.g. <code>2050_SSP245</code>, <code>2070_RCP85</code>.</p>
</div>

<h2>Step 2 - Algorithm Selection</h2>
<div class="step">
<p><span class="badge">2</span> Select which algorithms to use for the projection.</p>
</div>

<h2>Step 3 - Add Future Rasters</h2>
<div class="step">
<p><span class="badge">3</span> Click <b>Add Rasters...</b> to add future climate raster files.</p>
</div>
<div class="warn">
<b>Critical:</b> Add only <b>continuous</b> rasters in the <b>same order</b> as the variables
selected in the Variables tab. The banner at the top shows the required order.
</div>

<h2>Step 4 - Run</h2>
<div class="step">
<p><span class="badge">4</span> Click <b>Run Projection</b>. Results appear in the table and map viewer.</p>
</div>

<div class="tip"><b>Tip:</b> To add multiple scenarios, repeat the steps - each scenario must have a unique name.</div>
"""

EN_RANGE = _CSS + """
<h1>5 Range Change - Distribution Change Analysis</h1>

<h2>What is this Tab For?</h2>
<div class="box">
<p>Compare current and future <b>binary (0/1) maps</b> to calculate how much area the species
will <b>lose</b>, <b>gain</b>, or <b>retain</b>.</p>
</div>

<h2>Result Codes</h2>
<table>
<tr><th>Code</th><th>Colour</th><th>Meaning</th></tr>
<tr><td>-2</td><td style="color:#f03b20">Red</td><td>Lost area (present now, absent in future)</td></tr>
<tr><td>0</td><td style="color:#aaa">Grey</td><td>Stable absence (absent in both periods)</td></tr>
<tr><td>1</td><td style="color:#99d8c9">Light Green</td><td>Stable presence (present in both periods)</td></tr>
<tr><td>2</td><td style="color:#2ca25f">Dark Green</td><td>Gained area (absent now, present in future)</td></tr>
</table>

<h2>Step 1 - Select Files</h2>
<div class="step">
<p><span class="badge">1</span> <b>Current projection</b>: Baseline binary raster.</p>
<p><span class="badge">2</span> <b>Future projection</b>: Future binary raster.</p>
<p><span class="badge">3</span> Use the <b>Quick Fill</b> section to populate fields from completed projections.</p>
</div>

<h2>Step 2 - Run</h2>
<div class="step">
<p><span class="badge">4</span> Click <b>Compute Range Change</b>. The statistics table and map are generated automatically.</p>
</div>

<h2>Reading the Results Table</h2>
<table>
<tr><th>Metric</th><th>Description</th></tr>
<tr><td>% Lost</td><td>Percentage of current range that will be lost</td></tr>
<tr><td>% Gained</td><td>Percentage of new area gained relative to current range</td></tr>
<tr><td>Net Change</td><td>Positive = range expansion, Negative = range contraction</td></tr>
</table>
"""

EN_EVAL = _CSS + """
<h1>6 Evaluation - Model Evaluation</h1>

<h2>Sub-Tabs</h2>
<table>
<tr><th>Sub-Tab</th><th>Content</th></tr>
<tr><td>Model Scores</td><td>ROC-AUC, TSS, Boyce values for all models</td></tr>
<tr><td>ROC Curves</td><td>ROC curve plot for each algorithm</td></tr>
<tr><td>Variable Importance</td><td>Permutation-based variable importance bar chart</td></tr>
<tr><td>Response Curves</td><td>Marginal response curve for each variable</td></tr>
<tr><td>Boyce Index</td><td>Continuous Boyce index (F-ratio curve)</td></tr>
<tr><td>Thresholds</td><td>Optimal binary threshold values via 5 methods</td></tr>
</table>

<h2>ROC Curve</h2>
<div class="box">
<p>The ROC curve shows how much better the model performs compared to random prediction.
<b>AUC = 1.0</b> is perfect; <b>AUC = 0.5</b> equals random chance.</p>
</div>

<h2>Variable Importance</h2>
<div class="box">
<p>Each variable is randomly shuffled (permutation) in turn and the resulting drop in model
accuracy is measured. The larger the drop, the more important the variable.</p>
</div>

<h2>Response Curves</h2>
<div class="box">
<p>How does the probability of species presence change along each variable?
Invaluable for ecological interpretation.</p>
</div>

<h2>Threshold Methods</h2>
<table>
<tr><th>Method</th><th>Recommended Use</th></tr>
<tr><td>max_tss</td><td>Default for most SDM applications (recommended)</td></tr>
<tr><td>p10</td><td>Recommended for MaxEnt models</td></tr>
<tr><td>max_kappa</td><td>When prevalence-sensitivity matters</td></tr>
<tr><td>sens_spec_eq</td><td>When omission and commission errors are equally important</td></tr>
<tr><td>min_roi</td><td>Prevalence-independent alternative</td></tr>
</table>
"""

EN_ADVANCED = _CSS + """
<h1>2b Variables - Advanced Analysis</h1>

<p style="padding:0 20px; color:#74c69d;">Complementary multicollinearity
diagnostics beyond VIF + correlation.</p>

<h2>What does this sub-tab add?</h2>
<div class="box">
<p>The <b>Advanced Analysis</b> sub-tab provides four diagnostics that
complement the classical VIF + correlation approach: Condition Number, PCA,
LASSO (L1), and Ridge (L2). Each one offers a different perspective on
redundancy and variable importance.</p>
</div>

<h2>1. Condition Number (&kappa;)</h2>
<div class="box">
<p>A single scalar summarising overall multicollinearity severity
(Belsley et al. 1980). Computed as the ratio of the largest to the smallest
singular value of the standardised design matrix:</p>
<ul>
<li><code>&kappa; &lt; 30</code>: weak - variables are well-conditioned.</li>
<li><code>30 &le; &kappa; &lt; 100</code>: moderate - interpret coefficients with care.</li>
<li><code>100 &le; &kappa; &lt; 1000</code>: severe - drop redundant variables.</li>
<li><code>&kappa; &ge; 1000</code>: near-singular - at least two variables are almost
perfectly linearly dependent. Very common when all 19 WorldClim bio variables
are retained (e.g. <code>bio_7 = bio_5 - bio_6</code> exactly).</li>
</ul>
</div>

<h2>2. Principal Component Analysis (PCA)</h2>
<div class="box">
<p>Transforms the scaled predictors into orthogonal principal components.
The scree plot shows variance explained per component, the cumulative plot
marks the 80% threshold, and the loadings table identifies which variables
dominate each component. The variable with the highest |loading| on each of
the first K components (where the cumulative variance reaches 80%) is
flagged as <b>RECOMMENDED</b>; together they form a non-redundant subset.</p>
</div>

<h2>3. LASSO (L1 regularisation)</h2>
<div class="box">
<p>Performs <b>embedded variable selection</b>: as the regularisation
strength &alpha; increases, coefficients of redundant variables are shrunk
exactly to zero. HABITUS runs <code>LassoCV</code> to find the
cross-validated optimal &alpha;, then refits at the user-selected &alpha;
(default 0.01). Variables with non-zero coefficients are flagged as
<b>SELECTED</b>.</p>
<p>The coefficient-path plot shows how every variable's weight evolves
across &alpha;. Both the CV-optimal (red dotted) and user-selected (orange
dashed) &alpha; values are marked.</p>
</div>

<h2>4. Ridge (L2 regularisation)</h2>
<div class="box">
<p>Unlike LASSO, Ridge never shrinks a coefficient exactly to zero - all
variables are retained but their weights are pulled towards zero. It is
stable under multicollinearity and provides a robust relative-importance
ranking. HABITUS uses <code>RidgeCV</code> to pick the optimal &alpha;.
Variables with <code>|coefficient|</code> above the median are flagged as
<b>RECOMMENDED</b>.</p>
</div>

<h2>How to combine the four methods</h2>
<table>
<tr><th>Step</th><th>Action</th></tr>
<tr><td>1</td><td>Look at Condition Number - if &kappa; &ge; 1000, the matrix is
near-singular. Drop redundant variables before trusting any coefficient.</td></tr>
<tr><td>2</td><td>Use PCA to understand variable groupings. Variables with the
highest |loading| on each PC form a non-redundant subset.</td></tr>
<tr><td>3</td><td>Use LASSO for automatic feature selection. Variables that
survive at both the user and CV-best &alpha; are robust choices.</td></tr>
<tr><td>4</td><td>Cross-check with Ridge: variables that are RECOMMENDED by
PCA, LASSO, and Ridge simultaneously are your safest core set.</td></tr>
</table>

<h2>Exporting results</h2>
<div class="step">
<p><span class="badge">1</span> Click <b>Save All Results...</b> to export
all plots (PNG at 300 DPI) and tables (CSV) to
<code>output_dir/advanced_analysis/</code>.</p>
</div>

<div class="tip"><b>Tip:</b> Combine this tab with the classical VIF +
correlation analysis. The Variables tab produces one final checklist which
is the actual input to the Models tab.</div>
"""

EN_VALIDATION = _CSS + """
<h1>7 Validation - Accuracy Assessment</h1>

<p style="padding:0 20px; color:#74c69d;">Quantitative comparison between
two raster maps or against field-collected CSV points.</p>

<h2>What is this tab for?</h2>
<div class="box">
<p>The <b>Validation</b> tab evaluates how well a predicted habitat
suitability map agrees with (i) an independent reference raster or (ii) a
CSV file containing field-validated occurrence/abundance records. It is
used to quantify model generalisation across datasets, algorithms, or time
periods.</p>
</div>

<h2>Step 1 - Map selection</h2>
<div class="step">
<p><span class="badge">1</span> Both layer combos auto-populate from
<code>output_dir</code> when model training finishes; alternatively use
<b>Browse...</b> to select any GeoTIFF.</p>
<p><span class="badge">2</span> Select one map as the <b>Reference</b>
(ground truth) and another as the <b>Validation</b> (prediction to be
assessed).</p>
</div>

<h2>Step 2 - Reclassification settings</h2>
<div class="box">
<p>Continuous 0-1 probability surfaces are reclassified into N equal-interval
classes before the accuracy metrics are computed. The user specifies:</p>
<ul>
<li><b>Number of classes</b> (2-10, default 5).</li>
<li><b>Lower threshold</b> for each map independently (default 0.20). Class 1
covers [0, lower_threshold]; the remaining range [lower_threshold, 1.0] is
split into equal intervals. Setting this to the max_TSS threshold (from the
Evaluation tab) aligns the reclassification with the binary-presence cut-off.</li>
</ul>
<p>The live break-point preview updates as the user adjusts the spin boxes.</p>
</div>

<h2>Step 3 - Sampling settings</h2>
<table>
<tr><th>Method</th><th>Description</th></tr>
<tr><td>Random</td><td>Uniformly random pixel selection over the reference
raster.</td></tr>
<tr><td>Stratified</td><td>Equal number of samples per reclassified class.</td></tr>
<tr><td>Systematic</td><td>Regular grid of sampling points.</td></tr>
<tr><td>CSV File</td><td>Read id, x, y, reference_value from a CSV file.
Points outside the validation raster extent are skipped automatically.</td></tr>
</table>

<h2>Step 4 - Run validation</h2>
<div class="step">
<p><span class="badge">3</span> Click <b>Run Validation</b>. HABITUS
reclassifies both rasters with the appropriate break points, extracts the
sampled cell values, computes the metrics, and renders the report inside
the results panel.</p>
</div>

<h2>Metrics reported</h2>
<table>
<tr><th>Group</th><th>Metrics</th></tr>
<tr><td>Primary</td><td>Overall Accuracy (OA), Cohen's Kappa (&kappa;),
F1-Score (macro and weighted), Precision (macro), Recall (macro).</td></tr>
<tr><td>Regression (raw 0-1 values)</td><td>R&sup2;, RMSE, MAE, Bias.</td></tr>
<tr><td>Per-class</td><td>Precision, Recall, F1-Score, Support for each of
the N reclassified classes.</td></tr>
<tr><td>Producer / User</td><td>Producer's accuracy (recall) and User's
accuracy (precision) per class.</td></tr>
<tr><td>Confusion Matrix</td><td>N x N table of predicted vs. reference
class counts.</td></tr>
</table>

<h2>Step 5 - Export</h2>
<div class="step">
<p><span class="badge">4</span> <b>Save Report</b> exports the full report
as TXT, JSON, or HTML. <b>Save Points CSV</b> exports the sampled points
with their reference and validation values (useful for manual inspection or
third-party re-analysis).</p>
<p>Reclassified rasters are also saved to
<code>output_dir/validation/Reclassify_ref_*.tif</code> and
<code>Reclassify_val_*.tif</code> for GIS inspection.</p>
</div>

<h2>Kappa interpretation</h2>
<table>
<tr><th>Kappa</th><th>Agreement</th></tr>
<tr><td>&lt; 0</td><td>Poor (worse than chance)</td></tr>
<tr><td>0.0-0.2</td><td>Slight</td></tr>
<tr><td>0.2-0.4</td><td>Fair</td></tr>
<tr><td>0.4-0.6</td><td>Moderate</td></tr>
<tr><td>0.6-0.8</td><td>Substantial</td></tr>
<tr><td>0.8-1.0</td><td>Almost perfect</td></tr>
</table>

<div class="tip"><b>Tip:</b> Use the Validation tab to compare a HABITUS
prediction against (i) an expert-delineated polygon converted to a raster,
(ii) a published SDM for the same species, or (iii) a held-out CSV of
recent field observations.</div>
"""

EN_REPORT = _CSS + """
<h1>8 Report - Scientific HTML Report</h1>

<p style="padding:0 20px; color:#74c69d;">Generate a 10-section publication-ready scientific report
from your completed analysis.</p>

<h2>What is this Tab For?</h2>
<div class="box">
<p>The <b>Report</b> tab automatically compiles all analysis results — variable selection, methods,
model parameters, evaluation metrics, distribution maps, future projections, range change statistics,
and the session log — into a single self-contained <b>HTML file</b>. All figures are embedded
directly in the file using base64 encoding; no external dependencies are required to view the report.</p>
</div>

<h2>Report Sections</h2>
<table>
<tr><th>#</th><th>Section</th><th>Content</th></tr>
<tr><td>1</td><td>Study Summary</td><td>Species name, output folder, date, occurrence count, selected variables</td></tr>
<tr><td>2</td><td>Variable Selection</td><td>Correlation heatmap, PCA, LASSO, Ridge VIF charts; variable priority table with Q1-level interpretation</td></tr>
<tr><td>3</td><td>Methods</td><td>SDM methodology, algorithm references, data split strategy</td></tr>
<tr><td>4</td><td>Model Parameters</td><td>Hyperparameter table for each selected algorithm with explanations</td></tr>
<tr><td>5</td><td>Model Evaluation</td><td>ROC-AUC, TSS, Boyce, Kappa table; threshold values; per-metric scientific interpretation</td></tr>
<tr><td>6</td><td>Current Distribution Maps</td><td>PNG files saved by the user from the map viewer, with automatic captions</td></tr>
<tr><td>7</td><td>Future Projections</td><td>Future scenario PNG files grouped by period (7.1.1, 7.1.2, ...)</td></tr>
<tr><td>8</td><td>Range Change Analysis</td><td>Lost / Gained / Stable habitat area statistics</td></tr>
<tr><td>9</td><td>Validation</td><td>External validation metrics</td></tr>
<tr><td>10</td><td>Session Log</td><td>Complete session log with timing for all steps</td></tr>
</table>

<h2>Step 1 - Select Sections</h2>
<div class="step">
<p><span class="badge">1</span> Use the checkboxes on the left to choose which sections to include in the report.
All sections are selected by default.</p>
</div>

<h2>Step 2 - Generate</h2>
<div class="step">
<p><span class="badge">2</span> Click <b>&#8635; Generate Report</b>. The report is compiled and a
preview appears in the right panel.</p>
</div>

<h2>Step 3 - Export</h2>
<div class="step">
<p><span class="badge">3</span> Click <b>&#128190; Save HTML</b> to save the report to your output folder.
The file is named <code>{species}_report.html</code>.</p>
</div>

<div class="tip"><b>Maps in the report:</b> Section 6 uses the PNG files you saved from the
Distribution Map viewer (Tab ③). Save maps with meaningful filenames before generating the report —
the filename is used to infer the map type and caption automatically.</div>

<div class="tip"><b>New Analysis:</b> Generating the report again after a new analysis automatically
updates all sections with the new results — simply click Generate Report again.</div>

<h2>Map Quality</h2>
<div class="box">
<p>All maps rendered directly from GeoTIFF files (Sections 6–7) use a <b>geographic aspect ratio
correction</b> based on the cosine of the map's central latitude. This prevents the horizontal
stretching that occurs with plate carr&eacute;e projection at high latitudes, ensuring maps appear
in their correct geographic proportions.</p>
</div>
"""

EN_FAQ = _CSS + """
<h1>Frequently Asked Questions &amp; Troubleshooting</h1>

<h2>Errors</h2>

<h3>\"No Full models found for selected algorithms\"</h3>
<div class="box">
<p><b>Cause:</b> The selected algorithms failed during model training.</p>
<p><b>Solution:</b></p>
<ul>
<li>Check the log panel - which model failed?</li>
<li>If MaxEnt is selected: <code>pip install elapid</code></li>
<li>If XGBoost is selected: <code>pip install xgboost</code></li>
<li>Check occurrence record count - very few presence points may cause some models to fail</li>
</ul>
</div>

<h3>\"Cannot find raster files for selected variables\"</h3>
<div class="box">
<p><b>Cause:</b> Raster file names do not match the variable names shown in Variables tab.</p>
<p><b>Solution:</b> Spaces and special characters in file names are automatically converted to underscores.
<code>bio 1.tif</code> &rarr; <code>bio_1</code>. Verify your raster file names.</p>
</div>

<h3>\"Raster CRS mismatch\"</h3>
<div class="box">
<p><b>Solution:</b> Reproject all rasters to the same coordinate system (EPSG:4326 recommended).</p>
</div>

<h3>Application freezes / becomes unresponsive</h3>
<div class="box">
<p>Model training, projection, and VIF computation all run in the background - this is normal.
As long as the progress bar and log are updating, the process is still running. Please be patient.</p>
</div>

<h2>Performance Tips</h2>
<div class="tip"><b>For speed:</b> Use 1 PA repeat and 2 CV runs for initial tests. Increase later if results look good.</div>
<div class="tip"><b>For memory:</b> Monitor system RAM when using many high-resolution rasters.</div>
<div class="tip"><b>For accuracy:</b> Aim for at least 30 presence records. With fewer records, prefer MaxEnt or ENFA.</div>

<h2>Output Files</h2>
<table>
<tr><th>File / Folder</th><th>Description</th></tr>
<tr><td><code>current/EMwmean_prob.tif</code></td><td>Ensemble probability map (0–1)</td></tr>
<tr><td><code>current/EMwmean_bin.tif</code></td><td>Ensemble binary map (0/1)</td></tr>
<tr><td><code>figures/</code></td><td>ROC, variable importance, response curve, Boyce plots (PNG, 300 DPI)</td></tr>
<tr><td><code>figures/roc_curves/</code></td><td>Individual ROC curve per algorithm</td></tr>
<tr><td><code>figures/response_curves/</code></td><td>Individual response curve per algorithm &times; variable</td></tr>
<tr><td><code>figures/evaluation_scores.csv</code></td><td>ROC-AUC, TSS, Boyce, Kappa per algorithm + ensemble</td></tr>
<tr><td><code>figures/classification_thresholds.csv</code></td><td>Five-method optimal thresholds</td></tr>
<tr><td><code>occurrence_train.csv</code></td><td>Training data coordinates</td></tr>
<tr><td><code>occurrence_test.csv</code></td><td>Test data coordinates</td></tr>
<tr><td><code>{scenario}/EMwmean_prob.tif</code></td><td>Future projection map</td></tr>
<tr><td><code>range_change/range_change_{scenario}.tif</code></td><td>Range change map (-2, 0, 1, 2)</td></tr>
<tr><td><code>validation/</code></td><td>Reclassified reference and validation rasters</td></tr>
<tr><td><code>advanced_analysis/</code></td><td>PCA, LASSO, Ridge plots and CSV tables</td></tr>
<tr><td><code>{species}_report.html</code></td><td>Self-contained 10-section scientific HTML report</td></tr>
<tr><td><code>*.log</code></td><td>Timestamped session log with per-algorithm timing</td></tr>
</table>
"""

# ══════════════════════════════════════════════════════════════════════════════
# ABOUT PAGE
# ══════════════════════════════════════════════════════════════════════════════

_ABOUT_CSS = """
<style>
  body   { background:#f5faf7; color:#1c3328; font-family:'Arial',sans-serif; font-size:13px; margin:0; padding:0; }
  .card  { background:#ffffff; border:1px solid #b8d4c4; border-radius:10px; padding:28px 36px; margin:24px 40px; }
  h1     { color:#1d5235; font-size:22px; margin:0 0 4px 0; letter-spacing:1px; }
  .sub   { color:#3a7050; font-size:13px; margin:0 0 20px 0; }
  h2     { color:#1d5235; font-size:13px; font-weight:700; margin:18px 0 6px 0; border-bottom:1px solid #c4ddd0; padding-bottom:4px; }
  .row   { display:table; width:100%; margin:4px 0; }
  .lbl   { display:table-cell; color:#4a7060; font-size:12px; width:160px; vertical-align:top; padding-top:2px; }
  .val   { display:table-cell; color:#1c3328; font-size:12px; font-weight:600; }
  a      { color:#3a8c60; text-decoration:none; }
  a:hover{ text-decoration:underline; }
  .ai    { background:#eef7f2; border-left:4px solid #3a8c60; border-radius:0 6px 6px 0; padding:10px 14px; margin:16px 0 0 0; font-size:12px; color:#2a5c40; line-height:1.7; }
  .badge { display:inline-block; background:#d4ead9; color:#1d5235; border-radius:12px; padding:2px 12px; font-size:11px; font-weight:700; margin-right:6px; }
  .ver   { font-size:28px; font-weight:800; color:#1d5235; letter-spacing:2px; }
  hr     { border:none; border-top:1px solid #c4ddd0; margin:16px 0; }
</style>
"""

EN_ABOUT = _ABOUT_CSS + """
<div class="card">
  <div class="ver">HABITUS v1.0.0</div>
  <div class="sub">Habitat Analysis and Biodiversity Integrated Toolkit for Unified Species Distribution Modelling (SDM)</div>
  <hr>
  {UPDATE_BANNER}

  <h2>Developers</h2>
  <div class="row"><span class="lbl">Authors :</span><span class="val">[Removed for peer review]</span></div>
  <div class="row"><span class="lbl">Institution :</span><span class="val">[Removed for peer review]</span></div>
  <div class="row"><span class="lbl">Year :</span><span class="val">2026</span></div>
  <div class="row"><span class="lbl">Platform :</span><span class="val">Windows / macOS / Linux &mdash; Standalone Desktop</span></div>

  <h2>Citation</h2>
  <div style="background:#eef6f1;border-left:3px solid #3a8c60;padding:10px 14px;border-radius:4px;font-size:12px;color:#1c3328;line-height:1.7;">
    [Authors removed for peer review] (2026). <b>HABITUS: Habitat Analysis and Biodiversity Integrated
    Toolkit for Unified Species Distribution Modelling.</b> <i>Ecological Perspective</i>, [Technical Report].
    [DOI removed for peer review]
  </div>

  <h2>License &amp; Source Code</h2>
  <div class="row"><span class="lbl">License :</span><span class="val">MIT License</span></div>
  <div class="row"><span class="lbl">Source Code :</span><span class="val">[Removed for peer review]</span></div>

  <h2>Core Dependencies</h2>
  <div class="row"><span class="lbl">Interface :</span><span class="val">PyQt6</span></div>
  <div class="row"><span class="lbl">Mapping :</span><span class="val">matplotlib - rasterio</span></div>
  <div class="row"><span class="lbl">Modelling :</span><span class="val">scikit-learn - elapid - xgboost - lightgbm - catboost - pygam</span></div>
  <div class="row"><span class="lbl">Data :</span><span class="val">numpy - pandas - geopandas - shapely - pyproj</span></div>

  <div class="ai">
    <b>Development Note</b><br>
    AI-assisted coding tools were used during software development
    to support code implementation and optimization. The conceptual framework, algorithm design,
    and validation were fully developed and verified by the developers.
  </div>
</div>
"""

# ══════════════════════════════════════════════════════════════════════════════
# PAGE DEFINITIONS (English only)
# ══════════════════════════════════════════════════════════════════════════════

_PAGES = [
    ("Overview",             EN_OVERVIEW),
    ("1 Data",               EN_DATA),
    ("2 Variables",          EN_VIF),
    ("2b Advanced Analysis", EN_ADVANCED),
    ("3 Models",             EN_MODELS),
    ("4 Future",             EN_FUTURE),
    ("5 Range Change",       EN_RANGE),
    ("6 Evaluation",         EN_EVAL),
    ("7 Validation",         EN_VALIDATION),
    ("8 Report",             EN_REPORT),
    ("FAQ",                  EN_FAQ),
    ("About",                EN_ABOUT),
]

# ══════════════════════════════════════════════════════════════════════════════
# WIDGET
# ══════════════════════════════════════════════════════════════════════════════

_BROWSER_STYLE = """
    QTextBrowser { background:#f5faf7; border:none; color:#1c3328; }
    QScrollBar:vertical { background:#e8f2ec; width:8px; }
    QScrollBar::handle:vertical { background:#9cc4b0; border-radius:4px; }
    QScrollBar::add-line, QScrollBar::sub-line { width:0; height:0; }
"""


class HelpTab(QWidget):

    _ABOUT_IDX = 11  # 0-based index of About page (Overview, Data, Variables,
                     # Advanced, Models, Future, Range, Evaluation, Validation, Report, FAQ, About)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._browsers: list[QTextBrowser] = []
        self._update_banner = ""
        self._setup_ui()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top bar (update buttons only) ─────────────────────────────────
        top_bar = QWidget()
        top_bar.setStyleSheet("background:#e4f0e8; border-bottom:1px solid #b8d4c4;")
        tb = QHBoxLayout(top_bar)
        tb.setContentsMargins(12, 6, 12, 6)
        tb.setSpacing(6)
        tb.addStretch()

        # Check for updates button
        self._btn_update = QPushButton("Check for Updates")
        self._btn_update.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_update.setStyleSheet(
            "background:#ddeee6; color:#3a7050; border:1px solid #b8d4c4; "
            "border-radius:4px; padding:4px 12px; font-size:11px;"
        )
        self._btn_update.clicked.connect(self._manual_check)
        tb.addWidget(self._btn_update)

        # Apply update button
        self._btn_apply = QPushButton("Apply Update")
        self._btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_apply.setStyleSheet(
            "background:#3a8c60; color:#ffffff; border:none; "
            "border-radius:4px; padding:4px 12px; font-size:11px; font-weight:bold;"
        )
        self._btn_apply.setToolTip("Download latest code from GitHub (no reinstall needed)")
        self._btn_apply.clicked.connect(self._apply_update)
        self._btn_apply.setVisible(False)
        tb.addWidget(self._btn_apply)

        root.addWidget(top_bar)

        # ── Content tabs ──────────────────────────────────────────────────
        self._nav = QTabWidget()
        self._nav.setObjectName("sdm_tabs")
        self._nav.setTabPosition(QTabWidget.TabPosition.North)

        for title, html in _PAGES:
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            browser.setStyleSheet(_BROWSER_STYLE)
            browser.setHtml(html)
            self._browsers.append(browser)
            self._nav.addTab(browser, title)

        root.addWidget(self._nav, 1)

    # ── Update checker ────────────────────────────────────────────────────

    def _about_html(self):
        return EN_ABOUT.replace("{UPDATE_BANNER}", self._update_banner)

    def _refresh_about(self):
        self._browsers[self._ABOUT_IDX].setHtml(self._about_html())

    def set_update_checking(self):
        self._update_banner = (
            "<div style='color:#6b8f7a;font-size:11px;margin-bottom:8px;'>"
            "Checking for updates...</div>"
        )
        self._refresh_about()

    def set_update_available(self, latest: str, url: str):
        self._btn_apply.setVisible(True)
        self._update_banner = (
            f"<div style='"
            f"background:#fff3cd;border:1px solid #f0ad4e;border-radius:6px;"
            f"padding:10px 14px;margin-bottom:12px;'>"
            f"<b style='color:#7a5000;'>Update Available - v{latest}</b><br>"
            f"<span style='color:#5a3c00;font-size:11px;'>"
            f"A new release is available on GitHub."
            f"</span><br>"
            f"<a href='{url}' style='color:#1d4a32;font-weight:bold;'>"
            f"&rarr; {url}</a>"
            f"</div>"
        )
        self._refresh_about()

    def set_up_to_date(self, current: str):
        self._btn_apply.setVisible(False)
        self._update_banner = (
            f"<div style='color:#276749;font-size:11px;margin-bottom:8px;'>"
            f"You are using the latest version (v{current}).</div>"
        )
        self._refresh_about()

    def set_check_failed(self, reason: str):
        self._update_banner = (
            f"<div style='color:#999;font-size:10px;margin-bottom:6px;'>"
            f"Update check failed: {reason}</div>"
        )
        self._refresh_about()

    def _manual_check(self):
        from habitus.version import APP_VERSION, GITHUB_REPO
        from habitus.updater import UpdateChecker
        self.set_update_checking()
        checker = UpdateChecker(APP_VERSION, GITHUB_REPO, parent=self)
        checker.update_available.connect(self.set_update_available)
        checker.up_to_date.connect(self.set_up_to_date)
        checker.check_failed.connect(self.set_check_failed)
        checker.start()
        self._checker = checker

    def _apply_update(self):
        from habitus.version import GITHUB_REPO
        from habitus.updater import PatchDownloader
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self, "Apply Update",
            "Download latest code from GitHub?\n\n"
            "The application will need to be restarted after patching.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._btn_apply.setEnabled(False)
        self._btn_apply.setText("Downloading...")

        dlr = PatchDownloader(GITHUB_REPO, parent=self)

        def _on_progress(msg, pct):
            self._btn_apply.setText(f"Downloading... {pct}%")

        def _on_done(n_ok, n_fail):
            self._btn_apply.setEnabled(True)
            self._btn_apply.setText("Apply Update")
            if n_fail == 0:
                QMessageBox.information(
                    self, "Update Applied",
                    f"{n_ok} files downloaded successfully.\n\n"
                    f"Please restart HABITUS to use the updated code."
                )
                self._update_banner = (
                    "<div style='background:#d4edda;border:1px solid #28a745;"
                    "border-radius:6px;padding:10px;margin-bottom:12px;'>"
                    "<b style='color:#155724;'>Update applied. Restart to activate.</b>"
                    "</div>"
                )
                self._refresh_about()
                self._btn_apply.setVisible(False)
            else:
                QMessageBox.warning(
                    self, "Partial Update",
                    f"{n_ok} files updated, {n_fail} failed.\n"
                    f"Check your internet connection and try again."
                )

        def _on_error(msg):
            self._btn_apply.setEnabled(True)
            self._btn_apply.setText("Apply Update")
            QMessageBox.critical(self, "Update Error", msg)

        dlr.progress.connect(_on_progress)
        dlr.finished.connect(_on_done)
        dlr.error.connect(_on_error)
        dlr.start()
        self._downloader = dlr
