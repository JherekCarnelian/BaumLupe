"""Transform-Tab: XSL-Stylesheet wählen, Transformation starten, Ergebnis als XML-Tree anzeigen.

Nutzt saxonche (Saxon/C Python-Bindings) statt Node.js – keine externe Laufzeit nötig.
Die Transformation läuft in einem QThread, damit die UI nicht blockiert.
"""

import json
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QFileDialog, QMessageBox, QMenu,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut

# Shortcuts für "Links anspringen" – F3 bleibt primär, weitere als Alternativen
_JUMP_SHORTCUTS = ["F3", "Ctrl+Return", "Ctrl+Space"]

from ui.xml_tree import XmlTreeWidget

# Einstellungsdatei im Aufruf-Verzeichnis (Dot-File → in Dateimanagern versteckt)
_PREFS_FILE = Path.cwd() / ".xmlviewer_prefs.json"
_MAX_RECENT = 10


def _load_prefs() -> dict:
    """Liest die Einstellungsdatei; gibt leeres Dict zurück bei Fehler."""
    try:
        return json.loads(_PREFS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_prefs(prefs: dict) -> None:
    try:
        _PREFS_FILE.write_text(json.dumps(prefs, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_recent(prefs: dict) -> list[str]:
    """Extrahiert die Recent-XSL-Liste aus den Prefs; filtert fehlende Dateien."""
    paths = prefs.get("recent_xsl", [])
    return [p for p in paths if isinstance(p, str) and Path(p).is_file()]


class TransformWorker(QThread):
    """Führt die XSLT-Transformation in einem Hintergrund-Thread aus."""

    result_ready = Signal(str)  # Transformations-Ergebnis als String
    error = Signal(str)         # Fehlermeldung bei Fehler

    def __init__(self, xml_path: str, xsl_path: str):
        super().__init__()
        self._xml_path = xml_path
        self._xsl_path = xsl_path

    def run(self) -> None:
        try:
            from saxonche import PySaxonProcessor
            with PySaxonProcessor(license=False) as proc:
                xslt = proc.new_xslt30_processor()
                exe = xslt.compile_stylesheet(stylesheet_file=self._xsl_path)
                doc = proc.parse_xml(xml_file_name=self._xml_path)
                result = exe.transform_to_string(xdm_node=doc)
            if result is None:
                self.error.emit("Transformation ergab kein Ergebnis.")
            else:
                self.result_ready.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))


class TransformTab(QWidget):
    """Widget für die XSLT-Transformation."""

    navigate_to_source = Signal(int)  # DFS-Index des Quellknotens → Dual-Pane-Navigation

    def __init__(self, stylesheets_dir: str, parent=None):
        super().__init__(parent)
        self._stylesheets_dir = stylesheets_dir
        self._xml_path: str | None = None
        self._worker: TransformWorker | None = None
        self._tmp_path: str | None = None
        self._current_xsl: str | None = None
        self._prefs: dict = _load_prefs()
        self._recent: list[str] = _load_recent(self._prefs)
        self._setup_ui()
        self._refresh_stylesheet_list()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)

        # Toolbar
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Stylesheet:"))
        self._combo = QComboBox()
        self._combo.setMinimumWidth(220)
        toolbar.addWidget(self._combo)

        btn_browse = QPushButton("Durchsuchen…")
        btn_browse.clicked.connect(self._browse_xsl)
        toolbar.addWidget(btn_browse)

        toolbar.addSpacing(16)

        self._btn_transform = QPushButton("Transformieren")
        self._btn_transform.setDefault(True)
        self._btn_transform.clicked.connect(self._run_transform)
        toolbar.addWidget(self._btn_transform)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Ergebnis als XML-Tree – gleiche Komponente wie der Quell-Tab
        self._tree = XmlTreeWidget()
        layout.addWidget(self._tree)

        # Automatisch transformieren wenn Stylesheet gewechselt wird
        self._combo.currentIndexChanged.connect(self._auto_transform)

        # Shortcuts: zum Quellknoten im linken Pane springen
        for key in _JUMP_SHORTCUTS:
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(self._navigate_to_source)

        # Kontextmenü im Ergebnis-Tree
        self._tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._show_context_menu)

    def _refresh_stylesheet_list(self) -> None:
        self._combo.clear()
        stylesheets_dir = Path(self._stylesheets_dir).resolve()

        # Zuletzt verwendete externe Dateien zuerst (nicht im stylesheets-Verzeichnis)
        for path in self._recent:
            if Path(path).resolve().parent != stylesheets_dir:
                self._combo.addItem(f"\u2605 {Path(path).name}", path)

        # Dateien aus dem stylesheets-Verzeichnis
        for f in sorted(stylesheets_dir.glob("*.xsl")):
            self._combo.addItem(f.name, str(f))

        # Zuletzt verwendetes Stylesheet vorauswählen
        if self._recent:
            idx = self._combo.findData(self._recent[0])
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def set_xml_path(self, path: str) -> None:
        self._xml_path = path
        self._auto_transform()

    def set_xsl_path(self, path: str) -> None:
        """XSL-Stylesheet programmatisch vorauswählen (z.B. per CLI)."""
        idx = self._combo.findData(path)
        if idx == -1:
            self._combo.addItem(Path(path).name, path)
            idx = self._combo.count() - 1
        self._combo.setCurrentIndex(idx)  # löst currentIndexChanged → _auto_transform aus

    def _auto_transform(self) -> None:
        """Transformation starten wenn beide Eingaben vorhanden sind."""
        if self._xml_path and self._combo.currentData():
            self._run_transform()

    def _browse_xsl(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "XSL-Stylesheet wählen", self._stylesheets_dir,
            "XSLT Stylesheets (*.xsl *.xslt);;Alle Dateien (*)"
        )
        if not path:
            return
        idx = self._combo.findData(path)
        if idx == -1:
            self._combo.addItem(Path(path).name, path)
            idx = self._combo.count() - 1
        self._combo.setCurrentIndex(idx)

    def _run_transform(self) -> None:
        if not self._xml_path:
            QMessageBox.information(self, "Keine XML-Datei",
                                    "Bitte zuerst eine XML-Datei öffnen.")
            return
        xsl_path = self._combo.currentData()
        if not xsl_path:
            QMessageBox.information(self, "Kein Stylesheet",
                                    "Bitte ein XSL-Stylesheet wählen.")
            return

        self._btn_transform.setEnabled(False)
        self._tree.clear()

        # Laufenden Worker abbrechen
        if self._worker and self._worker.isRunning():
            self._worker.result_ready.disconnect()
            self._worker.error.disconnect()
            self._worker.quit()
            self._worker.wait()

        self._current_xsl = xsl_path
        self._worker = TransformWorker(self._xml_path, xsl_path)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, result: str) -> None:
        self._btn_transform.setEnabled(True)
        if self._current_xsl:
            self._add_to_recent(self._current_xsl)
        # Ergebnis in Tempfile schreiben und als XML-Tree laden
        tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False,
                                          mode="w", encoding="utf-8")
        tmp.write(result)
        tmp.close()
        self._tmp_path = tmp.name
        self._tree.load_xml(tmp.name)

    @property
    def result_tree(self):
        """Gibt den Ergebnis-Tree zurück (für Expand/Collapse aus dem Hauptmenü)."""
        return self._tree

    def apply_style_config(self, config: dict) -> None:
        """Gibt neue Stil-Einstellungen an den Ergebnis-Tree weiter."""
        self._tree.apply_style_config(config)

    def _on_error(self, message: str) -> None:
        self._btn_transform.setEnabled(True)
        QMessageBox.warning(self, "Transformationsfehler", message)

    def _show_context_menu(self, pos) -> None:
        """Kontextmenü bei Rechtsklick im Ergebnis-Tree."""
        item = self._tree.itemAt(pos)
        if item is None:
            return
        self._tree.setCurrentItem(item)

        has_children = item.childCount() > 0
        element = item.data(0, Qt.ItemDataRole.UserRole)
        has_src_idx = (element is not None and
                       "xmlview-src-idx" in element.attrib)

        menu = QMenu(self._tree)

        act_expand = menu.addAction("Ausklappen")
        act_expand.setEnabled(has_children and not item.isExpanded())
        act_expand.triggered.connect(lambda: item.setExpanded(True))

        act_collapse = menu.addAction("Einklappen")
        act_collapse.setEnabled(has_children and item.isExpanded())
        act_collapse.triggered.connect(lambda: item.setExpanded(False))

        menu.addSeparator()

        has_value = bool(element is not None and (element.text or "").strip())
        has_attrs = bool(element is not None and
                         any(k != "xmlview-src-idx" for k in element.attrib))

        act_xml = menu.addAction("XML kopieren        (Ctrl+C)")
        act_xml.triggered.connect(self._tree.copy_selected)
        act_val = menu.addAction("Wert kopieren       (Ctrl+Shift+C)")
        act_val.setEnabled(has_value)
        act_val.triggered.connect(self._tree.copy_value)
        act_attr = menu.addAction("Attribute kopieren  (Ctrl+Alt+C)")
        act_attr.setEnabled(has_attrs)
        act_attr.triggered.connect(self._tree.copy_attrs)

        menu.addSeparator()

        act_jump = menu.addAction("Links anspringen  (F3)")
        act_jump.setEnabled(has_src_idx)
        act_jump.triggered.connect(self._navigate_to_source)

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _navigate_to_source(self) -> None:
        """F3: xmlview-src-idx aus dem selektierten Ergebnis-Item lesen und Signal senden."""
        item = self._tree.currentItem()
        if item is None:
            return
        element = item.data(0, Qt.ItemDataRole.UserRole)  # ET.Element aus UserRole
        if element is None:
            return
        idx_str = element.attrib.get("xmlview-src-idx")
        if idx_str is None:
            return
        try:
            self.navigate_to_source.emit(int(idx_str))
        except ValueError:
            pass

    def _add_to_recent(self, path: str) -> None:
        """Fügt einen XSL-Pfad an den Anfang der Recent-Liste und speichert."""
        path = str(Path(path).resolve())
        self._recent = [p for p in self._recent if p != path]
        self._recent.insert(0, path)
        self._recent = self._recent[:_MAX_RECENT]
        self._prefs["recent_xsl"] = self._recent
        _save_prefs(self._prefs)
