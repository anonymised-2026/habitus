# -*- coding: utf-8 -*-
"""
Tab 3 – Ensemble Modelling
Equivalent to BIOMOD_EnsembleModeling()
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QDoubleSpinBox, QComboBox,
    QGroupBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QAbstractItemView, QHeaderView, QLabel
)
from PyQt6.QtGui import QColor


def _theme_fg(role: str):
    """Readable foreground color for both light and dark themes."""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QColor, QPalette
    bg = QApplication.instance().palette().color(QPalette.ColorRole.Window)
    dark = bg.lightness() < 128
    table = {
        "ok":      ("#52b788", "#1a7a4a"),
        "warn":    ("#f6ad55", "#b45309"),
        "bad":     ("#fc8181", "#c0392b"),
        "neutral": ("#74c69d", "#0e6655"),
    }
    dark_c, light_c = table.get(role, ("#888888", "#444444"))
    return QColor(dark_c if dark else light_c)


class EnsembleTab(QWidget):

    def __init__(self, main_dialog):
        super().__init__()
        self.dlg = main_dialog
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Ensemble settings ──
        ens_group = QGroupBox("Ensemble Settings  (BIOMOD_EnsembleModeling)")
        ens_form  = QFormLayout(ens_group)

        self.eval_metric = QComboBox()
        self.eval_metric.addItems(["TSS", "ROC"])
        self.eval_metric.setToolTip("eval.metric – metric used to filter models")

        self.tss_threshold = QDoubleSpinBox()
        self.tss_threshold.setRange(0.0, 1.0)
        self.tss_threshold.setSingleStep(0.05)
        self.tss_threshold.setValue(0.7)
        self.tss_threshold.setDecimals(2)
        self.tss_threshold.setToolTip("eval.metric.quality.threshold – minimum score to include a model")

        self.chk_ca     = QCheckBox("Committee Averaging  (EMca)")
        self.chk_wmean  = QCheckBox("Weighted Mean  (EMwmean)")
        self.chk_ca.setChecked(True)
        self.chk_wmean.setChecked(True)

        ens_form.addRow("Evaluation metric:", self.eval_metric)
        ens_form.addRow("Quality threshold:", self.tss_threshold)
        ens_form.addRow("", self.chk_ca)
        ens_form.addRow("", self.chk_wmean)
        layout.addWidget(ens_group)

        # ── Ensemble results ──
        res_group  = QGroupBox("Ensemble Evaluation Scores")
        res_layout = QVBoxLayout(res_group)

        self.ens_info  = QLabel("Ensemble not yet built.")
        res_layout.addWidget(self.ens_info)

        self.ens_table = QTableWidget(0, 3)
        self.ens_table.setHorizontalHeaderLabels(["Ensemble Method", "ROC-AUC", "TSS"])
        self.ens_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.ens_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ens_table.setAlternatingRowColors(True)
        res_layout.addWidget(self.ens_table)
        layout.addWidget(res_group, 1)

        layout.addStretch()

        btn_run = QPushButton("▶  Build Ensemble Models")
        btn_run.clicked.connect(self._run)
        layout.addWidget(btn_run)

    def _run(self):
        modeler = self.dlg.state.get("modeler")
        if modeler is None:
            self.dlg.show_error("Please run individual models first.")
            return

        methods = []
        if self.chk_ca.isChecked():    methods.append("committee_averaging")
        if self.chk_wmean.isChecked(): methods.append("weighted_mean")
        if not methods:
            self.dlg.show_error("Select at least one ensemble method.")
            return

        self.dlg.set_progress("Building ensemble models…", 10)

        from habitus.sdm_core import EnsembleModeler
        from habitus.main_dialog import WorkerThread

        em = EnsembleModeler(
            modeler            = modeler,
            eval_metric        = self.eval_metric.currentText(),
            quality_threshold  = self.tss_threshold.value(),
            methods            = methods,
            progress_callback  = self.dlg.set_progress
        )

        # Evaluate on pooled PA data
        import numpy as np
        import pandas as pd
        pa_datasets = self.dlg.state["pa_datasets"]
        var_names   = self.dlg.state["var_names"]
        X_all = pd.concat([ds[0] for ds in pa_datasets], ignore_index=True)
        y_all = np.concatenate([ds[1] for ds in pa_datasets])
        X_arr = X_all[var_names].dropna().values

        def task(progress_cb):
            progress_cb("Building ensemble...", 20)
            em._filter_models()
            progress_cb("Evaluating ensemble...", 60)
            scores = em.evaluate(X_arr, y_all[:len(X_arr)])
            progress_cb("Ensemble complete.", 100)
            return em, scores

        self._worker = WorkerThread(task)
        self._worker.progress.connect(self.dlg.set_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(lambda e: self.dlg.show_error(f"Ensemble failed:\n{e}"))
        self._worker.start()

    def _on_done(self, result):
        em, scores = result
        self.dlg.state["ensemble"] = em

        n_sel = len(em.selected_keys)
        self.ens_info.setText(
            f"Models passing threshold: {n_sel} / "
            f"{len(em.modeler.fitted_models)}  "
            f"(threshold = {em.quality_threshold})"
        )

        self.ens_table.setRowCount(0)
        method_labels = {"ca": "Committee Averaging (EMca)",
                         "wmean": "Weighted Mean (EMwmean)"}
        for key, sc in scores.items():
            r = self.ens_table.rowCount()
            self.ens_table.insertRow(r)
            self.ens_table.setItem(r, 0, QTableWidgetItem(method_labels.get(key, key)))
            for ci, metric in [(1, "ROC"), (2, "TSS")]:
                val = sc.get(metric, float("nan"))
                item = QTableWidgetItem(f"{val:.4f}" if val == val else "N/A")
                if val == val:
                    if val >= 0.8:   item.setForeground(_theme_fg("ok"))
                    elif val >= 0.6: item.setForeground(_theme_fg("warn"))
                    else:            item.setForeground(_theme_fg("bad"))
                self.ens_table.setItem(r, ci, item)

        self.dlg.set_progress(f"Ensemble complete. {n_sel} models selected.", 100)
        self.dlg.unlock_tab(self.dlg.TAB_FUTURE)
        self.dlg.goto_tab(self.dlg.TAB_FUTURE)
