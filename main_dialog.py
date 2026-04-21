# -*- coding: utf-8 -*-
"""HABITUS – Main Dialog  (v2 — simplified workflow)"""

import os, traceback, datetime
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QPushButton, QLabel, QProgressBar, QTextEdit, QMessageBox, QSizePolicy,
    QScrollArea, QFrame, QFileDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from habitus.tabs.tab_data       import DataTab
from habitus.tabs.tab_vif        import VifTab
from habitus.tabs.tab_models     import ModelsTab
from habitus.tabs.tab_projection import ProjectionTab   # Future Scenarios
from habitus.tabs.tab_range      import RangeChangeTab
from habitus.tabs.tab_evaluation import EvaluationTab
from habitus.tabs.tab_validation import ValidationTab
from habitus.tabs.tab_report     import ReportTab
from habitus.tabs.tab_help       import HelpTab
from habitus.version             import APP_VERSION, GITHUB_REPO
from habitus.updater             import UpdateChecker


class WorkerThread(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(object)
    error    = pyqtSignal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn; self.args = args; self.kwargs = kwargs

    def _emit_progress(self, message, value):
        self.progress.emit(str(message), int(value))

    def run(self):
        try:
            result = self.fn(self._emit_progress, *self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception:
            self.error.emit(traceback.format_exc())


class SDMMainDialog(QDialog):

    # Tab indices
    TAB_DATA       = 0
    TAB_VIF        = 1
    TAB_MODELS     = 2   # includes current map
    TAB_FUTURE     = 3   # future climate scenarios
    TAB_RANGE      = 4
    TAB_EVALUATION = 5
    TAB_VALIDATION = 6
    TAB_REPORT     = 7

    def __init__(self, parent=None):
        super().__init__(parent)
        self._log_fh = None   # file handle for the session log
        self._setup_ui()
        self.state = self._fresh_state()
        # Inject state into all map viewers so save dialog knows species+layer
        for tab in (self.tab_models, self.tab_future, self.tab_range):
            if hasattr(tab, "map_viewer"):
                tab.map_viewer.set_app_state(self.state)
        # Set application-wide font to Arial for consistent appearance
        from PyQt6.QtGui import QFont as _QF
        app_font = _QF("Arial", 10)
        from PyQt6.QtWidgets import QApplication as _QA
        if _QA.instance():
            _QA.instance().setFont(app_font)
        self._apply_stylesheet()
        self.setWindowTitle("HABITUS")
        # Window flags — minimize + maximize butonları
        # Qt.Window flag'i: bağımsız pencere gibi davran (QGIS parent'ından bağımsız)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
        )
        # Ekran boyutuna göre pencere boyutunu ayarla
        try:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().availableGeometry()
            # Use larger default so screenshots are publication-quality
            w = min(1600, int(screen.width()  * 0.95))
            h = min(1000, int(screen.height() * 0.92))
            self.resize(w, h)
        except Exception:
            self.resize(1400, 900)

        # Startup update check (background — non-blocking)
        self._start_update_check()

    def _start_update_check(self):
        self.tab_help.set_update_checking()
        self._update_checker = UpdateChecker(APP_VERSION, GITHUB_REPO, parent=self)
        self._update_checker.update_available.connect(self._on_update_available)
        self._update_checker.up_to_date.connect(self.tab_help.set_up_to_date)
        self._update_checker.check_failed.connect(self.tab_help.set_check_failed)
        self._update_checker.start()

    def _on_update_available(self, latest: str, url: str):
        self.tab_help.set_update_available(latest, url)
        # Also show a brief notice in the main log
        self.log(f"🆕 HABITUS v{latest} is available at {url}")

    def _setup_ui(self):
        main = QVBoxLayout(self); main.setSpacing(0); main.setContentsMargins(0,0,0,0)

        # Header
        header = QWidget(); header.setObjectName("sdm_header")
        hl = QHBoxLayout(header); hl.setContentsMargins(16,10,16,10)
        t = QLabel("HABITUS"); t.setObjectName("sdm_title")
        s = QLabel("Habitat Analysis & Biodiversity Integrated Toolkit for USDM")
        s.setObjectName("sdm_subtitle")
        btn_reset = QPushButton("⟳ New Analysis")
        btn_reset.setObjectName("btn_danger")
        btn_reset.setMinimumWidth(155)
        btn_reset.setToolTip("Clear all loaded data and start a new analysis")
        btn_reset.clicked.connect(self._confirm_reset)

        # Small camera-icon screenshot button
        from PyQt6.QtGui import QKeySequence, QShortcut, QPixmap, QPainter, QColor, QIcon
        from PyQt6.QtCore import QSize
        btn_shot = QPushButton()
        btn_shot.setObjectName("btn_icon")
        btn_shot.setFixedSize(32, 32)
        btn_shot.setIconSize(QSize(18, 18))
        # Draw a compact camera glyph on a transparent pixmap
        pm = QPixmap(32, 32)
        pm.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#1d5235"))
        painter.setBrush(QColor("#ffffff"))
        # Camera body
        painter.drawRoundedRect(3, 10, 26, 18, 3, 3)
        # Small lens bump on top
        painter.drawRoundedRect(11, 6, 10, 5, 2, 2)
        # Lens circle
        painter.setBrush(QColor("#3a8c60"))
        painter.drawEllipse(10, 13, 12, 12)
        painter.setBrush(QColor("#1d5235"))
        painter.drawEllipse(13, 16, 6, 6)
        painter.end()
        btn_shot.setIcon(QIcon(pm))
        btn_shot.setToolTip(
            "Save the current HABITUS window as a 300 DPI PNG "
            "inside the active analysis folder (Ctrl+Shift+S).")
        btn_shot.clicked.connect(self._save_window_screenshot)
        QShortcut(QKeySequence("Ctrl+Shift+S"), self, self._save_window_screenshot)

        hl.addWidget(t); hl.addWidget(s); hl.addStretch()
        hl.addWidget(btn_shot)
        hl.addWidget(btn_reset)
        main.addWidget(header)

        # Tabs — 6 tabs, no separate Ensemble tab
        self.tabs = QTabWidget(); self.tabs.setObjectName("sdm_tabs")

        self.tab_data   = DataTab(self)
        self.tab_vif    = VifTab(self)
        self.tab_models = ModelsTab(self)
        self.tab_future = ProjectionTab(self)
        self.tab_range  = RangeChangeTab(self)
        self.tab_eval   = EvaluationTab(self)
        self.tab_valid  = ValidationTab(self)
        self.tab_report = ReportTab(self)
        self.tab_help   = HelpTab(self)

        # Her sekmeyi ScrollArea içine wrap et — küçük ekranlarda kaydırma sağlanır
        def _wrap(widget):
            sa = QScrollArea()
            sa.setWidget(widget)
            sa.setWidgetResizable(True)
            sa.setFrameShape(QFrame.Shape.NoFrame)
            sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            sa.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            return sa

        self.tabs.addTab(_wrap(self.tab_data),   "① Data")
        self.tabs.addTab(_wrap(self.tab_vif),    "② Variables")
        self.tabs.addTab(_wrap(self.tab_models), "③ Models + Current Map")
        self.tabs.addTab(_wrap(self.tab_future), "④ Future Scenarios")
        self.tabs.addTab(_wrap(self.tab_range),  "⑤ Range Change")
        self.tabs.addTab(_wrap(self.tab_eval),   "⑥ Evaluation")
        self.tabs.addTab(_wrap(self.tab_valid),  "⑦ Validation")
        self.tabs.addTab(_wrap(self.tab_report), "⑧ Report")
        self.tabs.addTab(self.tab_help,           "ⓘ Help")   # always enabled

        for i in range(1, 8):
            self.tabs.setTabEnabled(i, False)
        main.addWidget(self.tabs, 1)

        # Footer
        footer = QWidget(); footer.setObjectName("sdm_footer")
        fl = QVBoxLayout(footer); fl.setContentsMargins(8,4,8,4)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0,100); self.progress_bar.setValue(0)
        self.progress_bar.setObjectName("sdm_progress")
        self.progress_bar.setTextVisible(True); self.progress_bar.setFormat("Ready")
        self.log_view = QTextEdit()
        self.log_view.setObjectName("sdm_log"); self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(72); self.log_view.setFont(QFont("Arial", 9))
        self.log_view.setPlaceholderText("Log output will appear here…")
        fl.addWidget(self.progress_bar); fl.addWidget(self.log_view)
        main.addWidget(footer)

    def _apply_stylesheet(self):
        self.setStyleSheet("""
            /* ── Pastel Sage Green Theme ───────────────────────────────────── */

            /* Base */
            QDialog   { background: #f0f5f1; color: #1c3328; }
            QWidget   { background: #f0f5f1; color: #1c3328; }

            /* Header */
            #sdm_header {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #c8e6d4, stop:1 #ddf0e6);
                border-bottom: 2px solid #3a8c60;
            }
            #sdm_title    { font-size: 20px; font-weight: 700; color: #1d5235; letter-spacing: 1px; }
            #sdm_subtitle { font-size: 11px; color: #3a7050; margin-left: 12px; margin-top: 4px; }

            /* Tabs — main */
            QTabWidget::pane { border: 1px solid #b8d4c4; background: #f0f5f1; }
            QTabBar::tab {
                background: #ddeee6; color: #4a7060;
                padding: 8px 14px; border: 1px solid #b8d4c4;
                border-bottom: none; margin-right: 2px;
                font-size: 11px; font-weight: 600;
            }
            QTabBar::tab:selected  { background: #ffffff; color: #1d5235; border-top: 2px solid #3a8c60; }
            QTabBar::tab:hover:!selected { background: #cce5d8; color: #1d5235; }
            QTabBar::tab:disabled  { color: #a8c4b4; background: #eaf4ee; }

            /* Sub-tabs (sdm_tabs objectName) */
            QTabWidget[objectName="sdm_tabs"] QTabBar::tab { font-size: 10px; padding: 6px 10px; }

            /* Buttons */
            QPushButton {
                background: #3a8c60; color: #ffffff;
                border: none; border-radius: 5px;
                padding: 8px 20px; font-size: 12px; font-weight: 600;
            }
            QPushButton:hover   { background: #4aa070; }
            QPushButton:pressed { background: #2a6a48; }
            QPushButton:disabled { background: #c8ddd2; color: #90b0a0; }

            QPushButton#btn_secondary {
                background: #ddeee6; color: #2a5c40;
                border: 1px solid #b0d0be;
            }
            QPushButton#btn_secondary:hover { background: #cce5d8; }

            QPushButton#btn_danger {
                background: #c8e0d0; color: #1d4a32;
                border: 1px solid #8ab4a0;
            }
            QPushButton#btn_danger:hover { background: #b4d4c0; }

            QPushButton#btn_icon {
                background: #ddeee6; border: 1px solid #b0d0be;
                border-radius: 6px; padding: 2px;
            }
            QPushButton#btn_icon:hover { background: #cce5d8; }

            /* Labels */
            QLabel { color: #1c3328; font-size: 12px; min-height: 24px; }

            /* Line edits / spinboxes / combos */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
                background: #ffffff; color: #1c3328;
                border: 1px solid #b8d4c4; border-radius: 4px;
                padding: 5px 8px; min-height: 26px; max-height: 32px;
            }
            QSpinBox    { min-width: 90px; }
            QComboBox   { min-width: 120px; }
            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #3a8c60; }

            /* CheckBox */
            QCheckBox { color: #1c3328; }
            QCheckBox::indicator {
                width: 14px; height: 14px;
                border: 1px solid #8ab8a0; background: #ffffff; border-radius: 3px;
            }
            QCheckBox::indicator:checked { background: #3a8c60; border-color: #2a6a48; }

            /* GroupBox */
            QGroupBox {
                border: 1px solid #b8d4c4; border-radius: 6px;
                margin-top: 10px; padding: 10px;
                color: #1d5235; font-weight: 600;
                background: #f8fcf9;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 6px; color: #1d5235;
            }

            /* Table */
            QTableWidget {
                background: #ffffff; color: #1c3328;
                gridline-color: #cce0d4; border: 1px solid #b8d4c4;
                alternate-background-color: #f0f8f3;
            }
            QTableWidget::item          { color: #1c3328; }
            QTableWidget::item:selected { background: #b8e0cc; color: #1c3328; }
            QHeaderView::section {
                background: #d4eadc; color: #1d5235;
                padding: 6px; border: 1px solid #b8d4c4; font-weight: 600;
            }

            /* List */
            QListWidget {
                background: #ffffff; color: #1c3328;
                border: 1px solid #b8d4c4; border-radius: 4px;
                font-size: 10px;
            }
            QListWidget::item          { color: #1c3328; padding: 3px 6px; }
            QListWidget::item:hover    { background: #e4f2ea; }
            QListWidget::item:selected { background: #b8e0cc; color: #1c3328; }

            /* Scrollbars */
            QScrollBar:vertical   { background: #e8f2ec; width: 8px; }
            QScrollBar:horizontal { background: #e8f2ec; height: 8px; }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #9cc4b0; border-radius: 4px; min-height: 20px; min-width: 20px;
            }
            QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover { background: #6aa890; }
            QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }

            /* Splitter */
            QSplitter::handle { background: #b8d4c4; }

            /* Footer */
            #sdm_footer { background: #e4f0e8; border-top: 1px solid #b8d4c4; }
            #sdm_progress {
                background: #ddeee6; border: 1px solid #b8d4c4;
                border-radius: 4px; height: 14px;
                text-align: center; color: #1c3328;
            }
            #sdm_progress::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #3a8c60, stop:1 #5ab880);
                border-radius: 3px;
            }
            #sdm_log {
                background: #f5faf7; color: #1d5235;
                border: 1px solid #b8d4c4; border-radius: 4px;
            }

            /* ComboBox dropdown */
            QComboBox QAbstractItemView {
                background: #ffffff; color: #1c3328;
                selection-background-color: #b8e0cc;
                selection-color: #1c3328;
                border: 1px solid #b8d4c4; outline: none;
            }
            QComboBox::drop-down { border: none; width: 20px; }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #3a8c60;
                margin-right: 6px;
            }

            /* var_frame (VIF checklist rows) */
            QFrame#var_frame { background: #eef7f2; border: 1px solid #c4ddd0; border-radius: 4px; }
            QFrame#var_frame:hover { background: #ddf0e6; border-color: #8ab8a0; }

            /* ScrollArea */
            QScrollArea { background: #f0f5f1; border: none; }
            QScrollArea > QWidget > QWidget { background: #f0f5f1; }

            /* SpinBox arrows */
            QSpinBox::up-button, QDoubleSpinBox::up-button,
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                background: #ddeee6; width: 16px; border: none;
            }
            QSpinBox::up-arrow,   QDoubleSpinBox::up-arrow   { border-bottom: 5px solid #3a8c60; border-left: 4px solid transparent; border-right: 4px solid transparent; }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow { border-top:    5px solid #3a8c60; border-left: 4px solid transparent; border-right: 4px solid transparent; }

            /* TextEdit (log) */
            QTextEdit { background: #f5faf7; color: #1d5235; border: 1px solid #b8d4c4; border-radius: 4px; }
        """)

    def _fresh_state(self):
        """Return a clean initial state dict."""
        return {
            "formatter": None, "pa_datasets": None, "var_names": [],
            "modeler": None, "ensemble": None,
            "projections": {}, "range_results": {}, "output_dir": "",
            "species_name": "",
        }

    def _confirm_reset(self):
        reply = QMessageBox.question(
            self, "New Analysis",
            "This will clear all loaded data, models, and results.\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.reset_all()

    def reset_all(self):
        """Hard-reset every tab's internal state so a new species starts completely fresh."""
        self._close_log_file()

        # ── Stop any running workers ───────────────────────────────────────────
        for tab in (self.tab_data, self.tab_models, self.tab_future, self.tab_range):
            w = getattr(tab, "_worker", None)
            if w is not None and w.isRunning():
                w.quit()
                w.wait(500)
            if hasattr(tab, "_worker"):
                tab._worker = None

        # ── Fresh shared state ─────────────────────────────────────────────────
        self.state = self._fresh_state()

        # ── Map viewers: clear all layers + scatter overlays ──────────────────
        for tab in (self.tab_models, self.tab_future, self.tab_range):
            if hasattr(tab, "map_viewer"):
                try:
                    tab.map_viewer.clear_all()
                    tab.map_viewer.set_app_state(self.state)
                except Exception:
                    pass

        # ── Re-lock tabs 1-7, go back to Data tab ─────────────────────────────
        for i in range(1, 8):
            self.tabs.setTabEnabled(i, False)
        self.tabs.setCurrentIndex(0)

        # ── Log + progress ─────────────────────────────────────────────────────
        self.log_view.clear()
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Ready")

        # ── Tab 0 — Data ──────────────────────────────────────────────────────
        try: self.tab_data.env_list.clear()
        except Exception: pass
        try: self.tab_data.cat_list.clear()
        except Exception: pass
        try: self.tab_data.occ_path.clear()
        except Exception: pass
        try: self.tab_data.out_dir.clear()
        except Exception: pass
        try: self.tab_models.out_dir.clear()
        except Exception: pass
        try:
            self.tab_data._csv_cols = None
            self.tab_data._col_preview.setText(
                "ℹ  The first 3 columns will always be used:  "
                "① Species name  ·  ② Longitude  ·  ③ Latitude")
            self.tab_data._col_preview.setStyleSheet(
                "color:#1c3328; background:#d4edda; border:1px solid #52b788;"
                "border-radius:4px; padding:5px 8px; font-size:11px;")
        except Exception: pass

        # ── Tab 1 — VIF ───────────────────────────────────────────────────────
        self.tab_vif._ranking_df = None
        self.tab_vif._corr_df    = None
        self.tab_vif._var_checks = {}
        self.tab_vif._safe_vars  = set()
        try:
            while self.tab_vif._checklist_layout.count() > 1:
                item = self.tab_vif._checklist_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        except Exception: pass
        try:
            self.tab_vif._safe_label.setText("")
            self.tab_vif._safe_label.setVisible(False)
        except Exception: pass
        try:
            self.tab_vif._pairs_table.setRowCount(0)
        except Exception: pass

        # ── Tab 2 — Models ────────────────────────────────────────────────────
        # (map_viewer already cleared above; nothing else persists between species)

        # ── Tab 3 — Future Projection ─────────────────────────────────────────
        try: self.tab_future.rast_list.clear()
        except Exception: pass
        try: self.tab_future.proj_name.setText("2050_SSP245")
        except Exception: pass
        try: self.tab_future.gcm_model.clear()
        except Exception: pass
        try: self.tab_future.out_subdir.clear()
        except Exception: pass

        # ── Tab 4 — Range Change ──────────────────────────────────────────────
        # map_viewer cleared above; no other persistent state

        # ── Tab 5 — Evaluation ────────────────────────────────────────────────
        try:
            self.tab_eval.sc_fig.clear()
            self.tab_eval.sc_canvas.draw()
        except Exception: pass
        try:
            self.tab_eval.roc_fig.clear()
            self.tab_eval.roc_canvas.draw()
        except Exception: pass
        try:
            self.tab_eval.om_fig.clear()
            self.tab_eval.om_canvas.draw()
        except Exception: pass
        try:
            self.tab_eval.vi_fig.clear()
            self.tab_eval.vi_canvas.draw()
        except Exception: pass

        # ── Tab 6 — Validation ────────────────────────────────────────────────
        try:
            self.tab_valid._results    = None
            self.tab_valid._points     = None
            self.tab_valid._ref_layers = {}
            self.tab_valid._val_layers = {}
        except Exception: pass

        self.log("All data cleared. Ready for a new analysis.")

    def reset_all_downstream_from_data(self):
        """Reset VIF tab + everything downstream when Data is re-run.

        Called automatically at the start of _run() in DataTab whenever a
        previous formatter already exists — i.e. the user changed rasters and
        clicked Run again.  Clears tabs 1-6 completely so no stale variables,
        models, or evaluation results are carried forward.
        """
        # ── Stop workers ──────────────────────────────────────────────────────
        for tab in (self.tab_models, self.tab_future, self.tab_range):
            w = getattr(tab, "_worker", None)
            if w is not None and w.isRunning():
                w.quit()
                w.wait(500)
            if hasattr(tab, "_worker"):
                tab._worker = None

        # ── Wipe all downstream shared state ─────────────────────────────────
        self.state["formatter"]     = None
        self.state["pa_datasets"]   = None
        self.state["var_names"]     = []
        self.state["modeler"]       = None
        self.state["ensemble"]      = None
        self.state["projections"]   = {}
        self.state["range_results"] = {}

        # ── Map viewers ───────────────────────────────────────────────────────
        for tab in (self.tab_models, self.tab_future, self.tab_range):
            if hasattr(tab, "map_viewer"):
                try:
                    tab.map_viewer.clear_all()
                    tab.map_viewer.set_app_state(self.state)
                except Exception:
                    pass

        # ── VIF tab ───────────────────────────────────────────────────────────
        self.tab_vif._ranking_df = None
        self.tab_vif._corr_df    = None
        self.tab_vif._var_checks = {}
        self.tab_vif._safe_vars  = set()
        try:
            while self.tab_vif._checklist_layout.count() > 1:
                item = self.tab_vif._checklist_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        except Exception: pass
        try:
            self.tab_vif._safe_label.setText("")
            self.tab_vif._safe_label.setVisible(False)
        except Exception: pass
        try:
            self.tab_vif._pairs_table.setRowCount(0)
        except Exception: pass

        # ── Models tab ────────────────────────────────────────────────────────
        try:
            self.tab_models.results_table.setRowCount(0)
            self.tab_models.sub.setCurrentIndex(0)
        except Exception: pass

        # ── Future Projection tab ─────────────────────────────────────────────
        try: self.tab_future.rast_list.clear()
        except Exception: pass
        try: self.tab_future.gcm_model.clear()
        except Exception: pass
        try: self.tab_future.out_subdir.clear()
        except Exception: pass

        # ── Evaluation tab ────────────────────────────────────────────────────
        for prefix in ("sc", "roc", "om", "vi"):
            try:
                getattr(self.tab_eval, f"{prefix}_fig").clear()
                getattr(self.tab_eval, f"{prefix}_canvas").draw()
            except Exception:
                pass

        # ── Validation tab ────────────────────────────────────────────────────
        try:
            self.tab_valid._results    = None
            self.tab_valid._points     = None
            self.tab_valid._ref_layers = {}
            self.tab_valid._val_layers = {}
        except Exception: pass

        # ── Re-lock tabs 1-7 ─────────────────────────────────────────────────
        for i in range(1, 8):
            self.tabs.setTabEnabled(i, False)

        self.log("Data inputs changed — all previous results cleared. "
                 "Re-running data formatting…")

    def reset_downstream(self):
        """Reset everything downstream of variable selection (Models → Validation).

        Called when the user re-confirms variable selection so that stale models,
        maps, and evaluation results from a previous run are fully discarded.
        """
        # ── Stop running workers (models / projection / range) ────────────────
        for tab in (self.tab_models, self.tab_future, self.tab_range):
            w = getattr(tab, "_worker", None)
            if w is not None and w.isRunning():
                w.quit()
                w.wait(500)
            if hasattr(tab, "_worker"):
                tab._worker = None

        # ── Wipe shared state keys produced by Models / Future / Range ────────
        self.state["modeler"]       = None
        self.state["ensemble"]      = None
        self.state["projections"]   = {}
        self.state["range_results"] = {}

        # ── Map viewers: clear all raster layers + scatter points ─────────────
        for tab in (self.tab_models, self.tab_future, self.tab_range):
            if hasattr(tab, "map_viewer"):
                try:
                    tab.map_viewer.clear_all()
                    tab.map_viewer.set_app_state(self.state)
                except Exception:
                    pass

        # ── Models tab ────────────────────────────────────────────────────────
        try:
            self.tab_models.results_table.setRowCount(0)
        except Exception: pass
        try:
            self.tab_models.sub.setCurrentIndex(0)   # back to Algorithm Settings
        except Exception: pass

        # ── Future Projection tab ─────────────────────────────────────────────
        try: self.tab_future.rast_list.clear()
        except Exception: pass
        try: self.tab_future.gcm_model.clear()
        except Exception: pass
        try: self.tab_future.out_subdir.clear()
        except Exception: pass

        # ── Evaluation tab: clear all figures ─────────────────────────────────
        for prefix in ("sc", "roc", "om", "vi"):
            try:
                getattr(self.tab_eval, f"{prefix}_fig").clear()
                getattr(self.tab_eval, f"{prefix}_canvas").draw()
            except Exception:
                pass

        # ── Validation tab ────────────────────────────────────────────────────
        try:
            self.tab_valid._results    = None
            self.tab_valid._points     = None
            self.tab_valid._ref_layers = {}
            self.tab_valid._val_layers = {}
        except Exception: pass

        # ── Re-lock tabs 3-7; keep Data (0), VIF (1), Models (2) unlocked ─────
        for i in (self.TAB_FUTURE, self.TAB_RANGE,
                  self.TAB_EVALUATION, self.TAB_VALIDATION, self.TAB_REPORT):
            self.tabs.setTabEnabled(i, False)

        self.log("Variable selection changed — downstream results cleared. "
                 "Re-run Models to continue.")

    def closeEvent(self, event):
        """Reset state when the dialog is closed so it starts fresh next time."""
        self._close_log_file()
        self.reset_all()
        event.accept()

    # ── Logging ───────────────────────────────────────────────────────────────

    def _open_log_file(self):
        """Create (or re-use) the session log file in the output directory."""
        if self._log_fh is not None:
            return
        out_dir = self.state.get("output_dir", "").strip()
        if not out_dir or not os.path.isdir(out_dir):
            return
        try:
            ts  = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            sp  = self.state.get("species_name", "").strip("_") or "habitus"
            fpath = os.path.join(out_dir, f"{sp}_{ts}.log")
            self._log_fh = open(fpath, "w", encoding="utf-8")
            header = (
                f"HABITUS Analysis Log\n"
                f"Species : {sp}\n"
                f"Started : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"{'='*60}\n"
            )
            self._log_fh.write(header)
            self._log_fh.flush()
        except Exception:
            self._log_fh = None

    def _close_log_file(self):
        if self._log_fh is not None:
            try:
                self._log_fh.write(
                    f"{'='*60}\n"
                    f"Closed  : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                )
                self._log_fh.close()
            except Exception:
                pass
            self._log_fh = None

    def set_progress(self, message, value):
        self.progress_bar.setValue(int(value))
        self.progress_bar.setFormat(f"{message}  {int(value)}%")
        self._log_direct(message)

    def _log_direct(self, message):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_view.append(f"▸ [{ts}] {message}")
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())
        # Write to file (lazily opens on first call after out_dir is known)
        self._open_log_file()
        if self._log_fh is not None:
            try:
                self._log_fh.write(f"[{ts}] {message}\n")
                self._log_fh.flush()
            except Exception:
                pass

    def log(self, msg): self._log_direct(msg)
    def unlock_tab(self, idx): self.tabs.setTabEnabled(idx, True)
    def goto_tab(self, idx): self.tabs.setCurrentIndex(idx)
    def show_error(self, msg): QMessageBox.critical(self, "HABITUS Error", msg)
    def show_info(self, msg):  QMessageBox.information(self, "HABITUS", msg)

    # ── Auto analysis folder helper ───────────────────────────────────────
    @staticmethod
    def _habitus_root_dir():
        """Return (and create) the top-level HABITUS folder in the user's
        Documents directory."""
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        if not os.path.isdir(docs):
            docs = os.path.expanduser("~")
        root = os.path.join(docs, "HABITUS")
        os.makedirs(root, exist_ok=True)
        return root

    @staticmethod
    def _make_analysis_dir(species_name: str):
        """Create a timestamped sub-folder named <species>_YYYYMMDD_HHMMSS
        inside Documents/HABITUS/."""
        import re, datetime
        sp = re.sub(r"[^\w.-]", "_", str(species_name or "analysis")).strip("_") or "analysis"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        full = os.path.join(SDMMainDialog._habitus_root_dir(),
                            f"{sp}_{ts}")
        os.makedirs(full, exist_ok=True)
        return full

    # ── 300-DPI window screenshot (header button + Ctrl+Shift+S) ──────────
    def _save_window_screenshot(self):
        """Capture the whole HABITUS window at 300 DPI and save as PNG
        directly inside the current analysis output folder (no dialog)."""
        try:
            import datetime
            out_dir = self.state.get("output_dir", "")
            if not out_dir or not os.path.isdir(out_dir):
                # Fall back to Documents/HABITUS/screenshots/
                out_dir = os.path.join(self._habitus_root_dir(), "screenshots")
            os.makedirs(out_dir, exist_ok=True)

            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            fpath = os.path.join(out_dir, f"HABITUS_{ts}.png")

            pixmap = self.grab()
            tmp = fpath + ".tmp.png"
            pixmap.save(tmp, "PNG")

            try:
                from PIL import Image
                img = Image.open(tmp)
                img.save(fpath, "PNG", dpi=(300, 300), optimize=True)
                w, h = img.size
                img.close()
                os.remove(tmp)
            except Exception:
                os.replace(tmp, fpath)
                w, h = pixmap.width(), pixmap.height()

            self.log(f"Screenshot saved ({w}x{h} @ 300 DPI): {fpath}")
            self.show_info(f"Screenshot saved ({w}x{h} @ 300 DPI):\n{fpath}")
        except Exception as exc:
            self.show_error(f"Could not save screenshot:\n{exc}")
