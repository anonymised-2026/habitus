# -*- coding: utf-8 -*-
"""
Tab 5 – Species Range Change
Equivalent to BIOMOD_RangeSize()
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLineEdit, QComboBox,
    QGroupBox, QLabel, QFileDialog, QTableWidget,
    QTableWidgetItem, QAbstractItemView, QHeaderView
)

from habitus.map_widget import RasterMapWidget


class RangeChangeTab(QWidget):

    def __init__(self, main_dialog):
        super().__init__()
        self.dlg = main_dialog
        self._worker = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        info = QLabel(
            "Compare binary (0/1) ensemble projections between two time periods.\n"
            "Result codes: –2 = Lost  |  0 = Stable Absent  |  1 = Stable Present  |  2 = Gained"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color:#74c69d; background:#0d1117; padding:8px; border-radius:4px;")
        layout.addWidget(info)

        # ── File pickers ──
        files_group  = QGroupBox("Input Binary Projection Rasters")
        files_layout = QFormLayout(files_group)

        self.current_path = QLineEdit()
        self.current_path.setPlaceholderText("Binary raster – current/baseline projection…")
        btn_cur = QPushButton("Browse…"); btn_cur.setObjectName("btn_secondary")
        btn_cur.clicked.connect(lambda: self._pick_raster(self.current_path))
        cur_row = QHBoxLayout(); cur_row.addWidget(self.current_path); cur_row.addWidget(btn_cur)

        self.future_path = QLineEdit()
        self.future_path.setPlaceholderText("Binary raster – future projection…")
        btn_fut = QPushButton("Browse…"); btn_fut.setObjectName("btn_secondary")
        btn_fut.clicked.connect(lambda: self._pick_raster(self.future_path))
        fut_row = QHBoxLayout(); fut_row.addWidget(self.future_path); fut_row.addWidget(btn_fut)

        files_layout.addRow("Current projection:", cur_row)
        files_layout.addRow("Future projection:",  fut_row)
        layout.addWidget(files_group)

        # ── Shortcut: auto-fill from projections ──
        auto_group  = QGroupBox("Quick Fill from Completed Projections")
        auto_layout = QFormLayout(auto_group)

        self.cb_current = QComboBox(); self.cb_current.addItem("— select —")
        self.cb_future  = QComboBox(); self.cb_future.addItem("— select —")
        btn_fill = QPushButton("Fill Paths")
        btn_fill.setObjectName("btn_secondary")
        btn_fill.clicked.connect(self._auto_fill)

        auto_layout.addRow("Current proj. key:", self.cb_current)
        auto_layout.addRow("Future proj. key:", self.cb_future)
        auto_layout.addRow("", btn_fill)
        layout.addWidget(auto_group)

        # ── Output ──
        out_group  = QGroupBox("Output")
        out_layout = QFormLayout(out_group)
        self.analysis_name = QLineEdit("SRC_current_future")
        out_layout.addRow("Analysis name:", self.analysis_name)
        layout.addWidget(out_group)

        # ── Stats table ──
        stats_group  = QGroupBox("Range Change Statistics")
        stats_layout = QVBoxLayout(stats_group)
        self.stats_table = QTableWidget(0, 2)
        self.stats_table.setHorizontalHeaderLabels(["Metric", "Value"])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stats_table.setAlternatingRowColors(True)
        stats_layout.addWidget(self.stats_table)
        layout.addWidget(stats_group)

        # ── Embedded map viewer ──
        from PyQt6.QtWidgets import QGroupBox as _GB
        map_view_grp = _GB("Range Change Map Viewer")
        map_view_layout = QVBoxLayout(map_view_grp)
        self.map_viewer = RasterMapWidget()
        self.map_viewer.setMinimumHeight(320)
        map_view_layout.addWidget(self.map_viewer)
        layout.addWidget(map_view_grp, 1)

        btn_run = QPushButton("▶  Compute Range Change")
        btn_run.clicked.connect(self._run)
        layout.addWidget(btn_run)

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_combos()

    def _refresh_combos(self):
        projections = self.dlg.state.get("projections", {})
        for cb in [self.cb_current, self.cb_future]:
            cb.clear(); cb.addItem("— select —")
        for proj_name, files in projections.items():
            for key, path in files.items():
                if "_bin" in key:
                    label = f"{proj_name} :: {key}"
                    self.cb_current.addItem(label, path)
                    self.cb_future.addItem(label, path)

    def _auto_fill(self):
        if self.cb_current.currentIndex() > 0:
            self.current_path.setText(self.cb_current.currentData())
        if self.cb_future.currentIndex() > 0:
            self.future_path.setText(self.cb_future.currentData())

    def _pick_raster(self, line_edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Binary Raster", "",
            "Raster files (*.tif *.tiff *.img *.asc)"
        )
        if path:
            line_edit.setText(path)

    def _run(self):
        cur = self.current_path.text().strip()
        fut = self.future_path.text().strip()
        if not cur or not fut:
            self.dlg.show_error("Please specify both current and future binary rasters.")
            return

        base_dir  = self.dlg.state.get("output_dir", ".")
        sp        = self.dlg.state.get("species_name", "").strip("_")
        prefix    = f"{sp}_" if sp else ""
        out_path  = os.path.join(base_dir, f"{prefix}{self.analysis_name.text().strip()}_SRC.tif")

        self.dlg.set_progress("Computing species range change…", 10)

        from habitus.sdm_core import RangeChangeAnalyzer
        from habitus.main_dialog import WorkerThread

        def task(progress_cb):
            progress_cb("Computing range change...", 20)
            result = RangeChangeAnalyzer.compute(cur, fut, out_path)
            progress_cb("Range change complete.", 100)
            return result

        self._worker = WorkerThread(task)
        self._worker.progress.connect(self.dlg.set_progress)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(lambda e: self.dlg.show_error(f"Range change failed:\n{e}"))
        self._worker.start()

    def _on_done(self, result):
        stats, out_path = result
        name = self.analysis_name.text().strip()
        self.dlg.state["range_results"][name] = (stats, out_path)

        self.stats_table.setRowCount(0)
        labels = {
            "Lost":           "Lost pixels (present → absent)",
            "Stable_Present": "Stable present pixels",
            "Stable_Absent":  "Stable absent pixels",
            "Gained":         "Gained pixels (absent → present)",
            "Total_Current":  "Total current range (pixels)",
            "Total_Future":   "Total future range (pixels)",
            "Pct_Lost":       "% Lost (of current range)",
            "Pct_Gained":     "% Gained (of current range)",
            "Net_Change":     "Net change (%)",
        }
        for key, label in labels.items():
            val = stats.get(key, "—")
            r = self.stats_table.rowCount()
            self.stats_table.insertRow(r)
            self.stats_table.setItem(r, 0, QTableWidgetItem(label))
            self.stats_table.setItem(r, 1, QTableWidgetItem(str(val)))

        # Display range change map in embedded viewer
        if os.path.isfile(out_path):
            self.map_viewer.load_raster(out_path, f"{name}_SRC", "range_change")

        self.dlg.set_progress("Range change analysis complete.", 100)

