"""Hauptfenster des XML-Viewers – Dual-Pane: XML-Eingabe links, mehrere Transform-Panes rechts.

Die rechte Seite enthält einen vertikalen QSplitter, der zur Laufzeit um weitere
TransformTab-Panes erweitert werden kann ("+"-Button). Jede Pane hat einen "✕"-Button
zum Schließen (mind. eine Pane bleibt immer bestehen).
"""

import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QStatusBar, QDialog,
    QAbstractItemView, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QApplication, QMessageBox,
)
from PySide6.QtCore import Qt, QSettings, Signal
from PySide6.QtGui import QAction, QKeySequence, QShortcut

from ui.xml_tree import XmlTreeWidget, load_style_config, save_style_config
from ui.transform_tab import TransformTab

_STYLESHEETS_DIR = str(Path(__file__).parent.parent / "stylesheets")

_SHARED_SETTINGS = QSettings("xmlviewer", "xmlviewer")


def _create_annotated_xml(path: str) -> str:
    """Parst die XML-Datei, fügt xmlview-src-idx auf jedem Element ein und
    schreibt das Ergebnis in eine temporäre Datei. Gibt den Temp-Pfad zurück.
    """
    tree = ET.parse(path)
    for idx, el in enumerate(tree.iter()):
        el.set("xmlview-src-idx", str(idx))
    tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".xml", delete=False)
    tree.write(tmp, encoding="utf-8", xml_declaration=True)
    tmp.close()
    return tmp.name


class _TransformPaneWrapper(QWidget):
    """TransformTab + Schließen-Button in einem dünnen Header-Strip."""

    remove_requested = Signal(object)  # sendet self

    def __init__(self, stylesheets_dir: str, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Dünner Header-Strip mit Close-Button ganz rechts
        strip = QWidget()
        strip.setFixedHeight(28)
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(6, 3, 4, 3)
        strip_layout.addStretch()
        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setToolTip("Pane schließen")
        self._close_btn.clicked.connect(lambda: self.remove_requested.emit(self))
        strip_layout.addWidget(self._close_btn)
        layout.addWidget(strip)

        self.transform_tab = TransformTab(stylesheets_dir=stylesheets_dir)
        layout.addWidget(self.transform_tab)

    def set_close_enabled(self, enabled: bool) -> None:
        self._close_btn.setEnabled(enabled)

    @property
    def result_tree(self):
        return self.transform_tab.result_tree


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XML Viewer")
        self.resize(1400, 700)

        self._geo_key = f"geometry_{os.getpid()}_{id(self)}"
        self._annotated_xml_tmp: str | None = None
        self._pane_wrappers: list[_TransformPaneWrapper] = []

        self._setup_ui()
        self._setup_menu()
        self._restore_geometry()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Linke Seite: XML-Eingabe ---
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        left_header = QWidget()
        left_header_layout = QHBoxLayout(left_header)
        left_header_layout.setContentsMargins(6, 4, 6, 4)
        self._xml_label = QLabel("(keine Datei geladen)")
        self._xml_label.setStyleSheet("color: gray;")
        left_header_layout.addWidget(self._xml_label, stretch=1)
        open_btn = QPushButton("XML öffnen…")
        open_btn.clicked.connect(self._open_file)
        left_header_layout.addWidget(open_btn)
        left_layout.addWidget(left_header)

        self._xml_tree = XmlTreeWidget()
        left_layout.addWidget(self._xml_tree)

        # --- Rechte Seite: Container mit "+ Pane"-Button + vertikaler Splitter ---
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        right_header = QWidget()
        right_header.setFixedHeight(34)
        right_header_layout = QHBoxLayout(right_header)
        right_header_layout.setContentsMargins(6, 4, 6, 4)
        right_header_layout.addStretch()
        add_btn = QPushButton("＋  Stylesheet-Pane")
        add_btn.setToolTip("Weitere Transform-Pane hinzufügen")
        add_btn.clicked.connect(self._add_transform_pane)
        right_header_layout.addWidget(add_btn)
        right_layout.addWidget(right_header)

        self._right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_layout.addWidget(self._right_splitter)

        self._splitter.addWidget(left_pane)
        self._splitter.addWidget(right_container)
        self._splitter.setSizes([500, 900])

        # Erste Pane automatisch anlegen
        self._add_transform_pane()

        # F6 / Ctrl+Tab: Fokus vorwärts; Ctrl+Shift+Tab: rückwärts
        for key in ("F6", "Ctrl+Tab"):
            sc = QShortcut(QKeySequence(key), self)
            sc.activated.connect(lambda: self._toggle_pane_focus(+1))
        sc_back = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        sc_back.activated.connect(lambda: self._toggle_pane_focus(-1))

        self.setCentralWidget(self._splitter)
        self.setStatusBar(QStatusBar())

    def _setup_menu(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&Datei")

        open_action = QAction("&Öffnen…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_file)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        quit_action = QAction("&Beenden", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        settings_menu = menubar.addMenu("&Einstellungen")
        style_action = QAction("&Stil…", self)
        style_action.triggered.connect(self._open_style_settings)
        settings_menu.addAction(style_action)

        view_menu = menubar.addMenu("&Ansicht")

        expand_action = QAction("Alle &ausklappen", self)
        expand_action.triggered.connect(self._expand_all)
        view_menu.addAction(expand_action)

        collapse_action = QAction("Alle &einklappen", self)
        collapse_action.triggered.connect(self._collapse_all)
        view_menu.addAction(collapse_action)

        # Hilfe ganz rechts – Windows-Konvention
        help_menu = menubar.addMenu("&Hilfe")
        shortcuts_action = QAction("&Tastaturkürzel…", self)
        shortcuts_action.setShortcut(QKeySequence(Qt.Key.Key_F1))
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("&Über…", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # Pane-Verwaltung
    # ------------------------------------------------------------------

    def _add_transform_pane(self, xsl_path: str | None = None) -> None:
        wrapper = _TransformPaneWrapper(stylesheets_dir=_STYLESHEETS_DIR)
        wrapper.remove_requested.connect(self._remove_transform_pane)
        wrapper.transform_tab.navigate_to_source.connect(self._on_navigate_to_source)
        self._right_splitter.addWidget(wrapper)
        self._pane_wrappers.append(wrapper)

        if self._annotated_xml_tmp:
            wrapper.transform_tab.set_xml_path(self._annotated_xml_tmp)

        if xsl_path:
            wrapper.transform_tab.set_xsl_path(xsl_path)

        self._update_close_buttons()
        self._update_tab_order()

    def _remove_transform_pane(self, wrapper: _TransformPaneWrapper) -> None:
        if len(self._pane_wrappers) <= 1:
            return  # Mindestens eine Pane behalten
        wrapper.transform_tab.navigate_to_source.disconnect(self._on_navigate_to_source)
        self._pane_wrappers.remove(wrapper)
        wrapper.setParent(None)
        wrapper.deleteLater()
        self._update_close_buttons()
        self._update_tab_order()

    def _update_close_buttons(self) -> None:
        """Close-Button deaktivieren wenn nur noch eine Pane vorhanden."""
        only_one = len(self._pane_wrappers) == 1
        for w in self._pane_wrappers:
            w.set_close_enabled(not only_one)

    def _update_tab_order(self) -> None:
        """Tab-Reihenfolge: xml_tree → result_tree jeder Pane → zurück."""
        widgets = [self._xml_tree] + [w.result_tree for w in self._pane_wrappers]
        for i in range(len(widgets) - 1):
            self.setTabOrder(widgets[i], widgets[i + 1])
        self.setTabOrder(widgets[-1], self._xml_tree)

    # ------------------------------------------------------------------
    # Hilfe
    # ------------------------------------------------------------------

    def _show_shortcuts(self) -> None:
        rows = [
            ("Allgemein",                   None),
            ("Datei öffnen",                "Ctrl+O"),
            ("Beenden",                     "Ctrl+Q"),
            ("Hilfe",                       "F1"),
            ("Navigation",                  None),
            ("Pane-Fokus vorwärts",          "Ctrl+Tab  ·  F6"),
            ("Pane-Fokus rückwärts",         "Ctrl+Shift+Tab"),
            ("Knoten auf-/zuklappen",       "Leertaste"),
            ("Alle ausklappen / einklappen","Ansicht-Menü"),
            ("Dual-Pane-Verknüpfung",       None),
            ("Zum Quellknoten springen",    "F3  ·  Ctrl+Return  ·  Ctrl+Space"),
            ("Kontextmenü (rechte Pane)",   "Rechtsklick → Ausklappen · Einklappen"),
            ("",                            "                  · Links anspringen"),
            ("Pane-Verwaltung",             None),
            ("Pane hinzufügen",             "＋-Button (rechts oben)"),
            ("Pane schließen",              "✕-Button (pro Pane)"),
        ]

        dlg = QDialog(self)
        dlg.setWindowTitle("Tastaturkürzel")
        dlg.setMinimumWidth(480)

        table = QTableWidget(len(rows), 2, dlg)
        table.setHorizontalHeaderLabels(["Aktion", "Kürzel"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setShowGrid(False)

        from PySide6.QtGui import QFont, QColor
        header_font = QFont()
        header_font.setBold(True)

        for r, (action, key) in enumerate(rows):
            is_header = key is None
            item_action = QTableWidgetItem(action)
            item_key    = QTableWidgetItem("" if is_header else key)
            if is_header:
                item_action.setFont(header_font)
                bg = QColor(220, 230, 245)
                item_action.setBackground(bg)
                item_key.setBackground(bg)
            table.setItem(r, 0, item_action)
            table.setItem(r, 1, item_key)

        table.resizeRowsToContents()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dlg.accept)

        layout = QVBoxLayout(dlg)
        layout.addWidget(table)
        layout.addWidget(buttons)

        dlg.exec()

    def _show_about(self) -> None:
        version = QApplication.applicationVersion()
        QMessageBox.about(
            self,
            "Über XML Viewer",
            f"<b>XML Viewer</b> {version}<br><br>"
            "Dual-Pane XML-Viewer mit XSLT 3.0 Transformation.<br>"
            "Mehrere Transform-Panes zur Laufzeit erweiterbar.<br><br>"
            "Tech-Stack: PySide6 · saxonche (Saxon/C)"
        )

    # ------------------------------------------------------------------
    # Ansicht
    # ------------------------------------------------------------------

    def _focused_tree(self):
        """Gibt den Tree zurück, der aktuell den Fokus hat."""
        focus = QApplication.focusWidget()
        if focus is None:
            return None
        if self._xml_tree.isAncestorOf(focus) or focus is self._xml_tree:
            return self._xml_tree
        for w in self._pane_wrappers:
            rt = w.result_tree
            if rt.isAncestorOf(focus) or focus is rt:
                return rt
        return None

    def _expand_all(self) -> None:
        tree = self._focused_tree()
        if tree:
            tree.expandAll()

    def _collapse_all(self) -> None:
        tree = self._focused_tree()
        if tree:
            tree.collapseAll()

    # ------------------------------------------------------------------
    # Einstellungen
    # ------------------------------------------------------------------

    def _open_style_settings(self) -> None:
        from ui.settings_dialog import SettingsDialog
        original = load_style_config()

        def preview(config: dict) -> None:
            self._xml_tree.apply_style_config(config)
            for w in self._pane_wrappers:
                w.transform_tab.apply_style_config(config)

        dlg = SettingsDialog(current_config=original, on_preview=preview, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            save_style_config(dlg.get_config())
            preview(dlg.get_config())
        else:
            preview(original)

    # ------------------------------------------------------------------
    # Laden
    # ------------------------------------------------------------------

    def _open_file(self) -> None:
        last_dir = _SHARED_SETTINGS.value("last_dir", str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(
            self, "XML-Datei öffnen", last_dir,
            "XML-Dateien (*.xml *.xhtml *.svg);;Alle Dateien (*)"
        )
        if not path:
            return
        _SHARED_SETTINGS.setValue("last_dir", str(Path(path).parent))
        self._load_xml(path)

    def _load_xml(self, path: str) -> None:
        self.setWindowTitle(f"XML Viewer – {Path(path).name}")
        self.statusBar().showMessage(f"Geladen: {path}")
        self._xml_label.setText(Path(path).name)
        self._xml_label.setStyleSheet("")

        self._xml_tree.load_xml(path)

        if self._annotated_xml_tmp:
            try:
                os.unlink(self._annotated_xml_tmp)
            except OSError:
                pass

        self._annotated_xml_tmp = _create_annotated_xml(path)
        for w in self._pane_wrappers:
            w.transform_tab.set_xml_path(self._annotated_xml_tmp)

    def _load_xsl(self, path: str) -> None:
        """XSL-Stylesheet in der ersten Pane vorauswählen (CLI-Argument)."""
        if self._pane_wrappers:
            self._pane_wrappers[0].transform_tab.set_xsl_path(path)

    def _toggle_pane_focus(self, direction: int = +1) -> None:
        """Fokus zyklisch durch alle Panes weiterschalten. direction: +1 vorwärts, -1 rückwärts."""
        focus = QApplication.focusWidget()
        trees = [self._xml_tree] + [w.result_tree for w in self._pane_wrappers]
        current = -1
        if focus is not None:
            for i, tree in enumerate(trees):
                if tree is focus or tree.isAncestorOf(focus):
                    current = i
                    break
        trees[(current + direction) % len(trees)].setFocus()

    def _on_navigate_to_source(self, idx: int) -> None:
        """Springt im linken XML-Tree zum Knoten mit dem gegebenen DFS-Index."""
        item = self._xml_tree.find_by_src_idx(idx)
        if item is None:
            return
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self._xml_tree.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtTop)
        self._xml_tree.setCurrentItem(item)

    # ------------------------------------------------------------------
    # Geometrie
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        geo = _SHARED_SETTINGS.value("geometry_last_multi")
        if geo:
            self.restoreGeometry(geo)
        splitter_state = _SHARED_SETTINGS.value("splitter_multi_h_last")
        if splitter_state:
            self._splitter.restoreState(splitter_state)
        right_state = _SHARED_SETTINGS.value("splitter_multi_v_last")
        if right_state:
            self._right_splitter.restoreState(right_state)

    def closeEvent(self, event) -> None:
        geo = self.saveGeometry()
        _SHARED_SETTINGS.setValue(self._geo_key, geo)
        _SHARED_SETTINGS.setValue("geometry_last_multi", geo)
        _SHARED_SETTINGS.setValue("splitter_multi_h_last", self._splitter.saveState())
        _SHARED_SETTINGS.setValue("splitter_multi_v_last", self._right_splitter.saveState())
        _SHARED_SETTINGS.remove(self._geo_key)
        if self._annotated_xml_tmp:
            try:
                os.unlink(self._annotated_xml_tmp)
            except OSError:
                pass
        super().closeEvent(event)
