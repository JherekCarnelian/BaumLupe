"""Hauptfenster des XML-Viewers – Dual-Pane: XML-Eingabe links, Transform-Ergebnis rechts."""

import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QSplitter, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QStatusBar, QDialog,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction, QKeySequence

from ui.xml_tree import XmlTreeWidget, load_style_config, save_style_config
from ui.transform_tab import TransformTab

_STYLESHEETS_DIR = str(Path(__file__).parent.parent / "stylesheets")

_SHARED_SETTINGS = QSettings("xmlviewer", "xmlviewer")


def _create_annotated_xml(path: str) -> str:
    """Parst die XML-Datei, fügt data-src-idx auf jedem Element ein und
    schreibt das Ergebnis in eine temporäre Datei. Gibt den Temp-Pfad zurück.

    Der DFS-Index (enumerate(tree.iter())) stimmt mit dem _src_idx_to_item-Dict
    in XmlTreeWidget überein – das ist die Brücke zwischen den beiden Panes.
    """
    tree = ET.parse(path)
    for idx, el in enumerate(tree.iter()):
        el.set("data-src-idx", str(idx))
    tmp = tempfile.NamedTemporaryFile(mode="wb", suffix=".xml", delete=False)
    tree.write(tmp, encoding="utf-8", xml_declaration=True)
    tmp.close()
    return tmp.name


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XML Viewer")
        self.resize(1200, 700)

        self._geo_key = f"geometry_{os.getpid()}_{id(self)}"
        self._annotated_xml_tmp: str | None = None

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

        # --- Rechte Seite: Transform-Ergebnis ---
        self._transform_pane = TransformTab(stylesheets_dir=_STYLESHEETS_DIR)

        self._splitter.addWidget(left_pane)
        self._splitter.addWidget(self._transform_pane)
        self._splitter.setSizes([600, 600])

        self._transform_pane.navigate_to_source.connect(self._on_navigate_to_source)

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

    # ------------------------------------------------------------------
    # Ansicht
    # ------------------------------------------------------------------

    def _focused_tree(self):
        """Gibt den Tree zurück, der aktuell den Fokus hat."""
        from PySide6.QtWidgets import QApplication
        focus = QApplication.focusWidget()
        if focus is not None:
            if self._xml_tree.isAncestorOf(focus) or focus is self._xml_tree:
                return self._xml_tree
            result_tree = self._transform_pane.result_tree
            if result_tree.isAncestorOf(focus) or focus is result_tree:
                return result_tree
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
            self._transform_pane.apply_style_config(config)

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

        # Linke Pane: Original-XML anzeigen + _src_idx_to_item aufbauen
        self._xml_tree.load_xml(path)

        # Alte annotierte Temp-Datei aufräumen
        if self._annotated_xml_tmp:
            try:
                os.unlink(self._annotated_xml_tmp)
            except OSError:
                pass

        # Python injiziert data-src-idx in eine Kopie → XSLT braucht nichts zu tun
        self._annotated_xml_tmp = _create_annotated_xml(path)
        self._transform_pane.set_xml_path(self._annotated_xml_tmp)

    def _load_xsl(self, path: str) -> None:
        self._transform_pane.set_xsl_path(path)

    def _on_navigate_to_source(self, idx: int) -> None:
        """Springt im linken XML-Tree zum Knoten mit dem gegebenen DFS-Index."""
        item = self._xml_tree.find_by_src_idx(idx)
        if item is None:
            return
        # Alle Vorfahren aufklappen
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
        geo = _SHARED_SETTINGS.value("geometry_last")
        if geo:
            self.restoreGeometry(geo)
        splitter_state = _SHARED_SETTINGS.value("splitter_dual_last")
        if splitter_state:
            self._splitter.restoreState(splitter_state)

    def closeEvent(self, event) -> None:
        geo = self.saveGeometry()
        _SHARED_SETTINGS.setValue(self._geo_key, geo)
        _SHARED_SETTINGS.setValue("geometry_last", geo)
        _SHARED_SETTINGS.setValue("splitter_dual_last", self._splitter.saveState())
        _SHARED_SETTINGS.remove(self._geo_key)
        if self._annotated_xml_tmp:
            try:
                os.unlink(self._annotated_xml_tmp)
            except OSError:
                pass
        super().closeEvent(event)
