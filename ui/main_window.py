"""Hauptfenster des XML-Viewers."""

import os
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QVBoxLayout,
    QFileDialog, QStatusBar, QDialog,
)
from PySide6.QtCore import QSettings
from PySide6.QtGui import QAction, QKeySequence

from ui.xml_tree import XmlTreeWidget, load_style_config, save_style_config
from ui.transform_tab import TransformTab

_STYLESHEETS_DIR = str(Path(__file__).parent.parent / "stylesheets")

# Gemeinsame Settings (last_dir) – zwischen Instanzen geteilt, kein Problem
_SHARED_SETTINGS = QSettings("xmlviewer", "xmlviewer")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("XML Viewer")
        self.resize(1100, 700)

        # Geometrie-Key ist pro Prozess eindeutig → mehrere Fenster überschreiben
        # sich nicht gegenseitig beim Schließen
        self._geo_key = f"geometry_{os.getpid()}_{id(self)}"

        self._setup_ui()
        self._setup_menu()
        self._restore_geometry()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)

        tree_container = QWidget()
        tree_layout = QVBoxLayout(tree_container)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        self._xml_tree = XmlTreeWidget()
        tree_layout.addWidget(self._xml_tree)
        self._tabs.addTab(tree_container, "XML-Baum")

        self._transform_tab = TransformTab(stylesheets_dir=_STYLESHEETS_DIR)
        self._tabs.addTab(self._transform_tab, "Transform")

        self.setCentralWidget(self._tabs)
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
        expand_action.triggered.connect(lambda: self._active_tree().expandAll())
        view_menu.addAction(expand_action)

        collapse_action = QAction("Alle &einklappen", self)
        collapse_action.triggered.connect(lambda: self._active_tree().collapseAll())
        view_menu.addAction(collapse_action)

    # ------------------------------------------------------------------
    # Laden
    # ------------------------------------------------------------------

    def _active_tree(self):
        """Gibt den Tree des aktuell sichtbaren Tabs zurück."""
        if self._tabs.currentWidget() is self._transform_tab:
            return self._transform_tab.result_tree
        return self._xml_tree

    def _open_style_settings(self) -> None:
        from ui.settings_dialog import SettingsDialog
        original = load_style_config()

        def preview(config: dict) -> None:
            self._xml_tree.apply_style_config(config)
            self._transform_tab.apply_style_config(config)

        dlg = SettingsDialog(current_config=original, on_preview=preview, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            save_style_config(dlg.get_config())
            preview(dlg.get_config())
        else:
            preview(original)  # Änderungen der Live-Vorschau zurückrollen

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
        self._xml_tree.load_xml(path)
        self._transform_tab.set_xml_path(path)
        self._tabs.setCurrentIndex(0)

    def _load_xsl(self, path: str) -> None:
        """XSL vorauswählen und direkt zum Transform-Tab wechseln."""
        self._transform_tab.set_xsl_path(path)
        self._tabs.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Geometrie – pro Instanz isoliert
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        # Fallback: letzte gespeicherte Geometrie irgendeiner Instanz
        geo = _SHARED_SETTINGS.value("geometry_last")
        if geo:
            self.restoreGeometry(geo)

    def closeEvent(self, event) -> None:
        geo = self.saveGeometry()
        # Unter instanz-eigenem Key speichern (kein Konflikt)
        _SHARED_SETTINGS.setValue(self._geo_key, geo)
        # Zusätzlich als "letzter Stand" für neue Fenster
        _SHARED_SETTINGS.setValue("geometry_last", geo)
        # Eigenen Key aufräumen
        _SHARED_SETTINGS.remove(self._geo_key)
        super().closeEvent(event)
