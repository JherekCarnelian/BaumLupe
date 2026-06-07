"""Transform-Tab: XSL-Stylesheet wählen, Transformation starten, Ergebnis als XML-Tree anzeigen.

Nutzt saxonche (Saxon/C Python-Bindings) statt Node.js – keine externe Laufzeit nötig.
Die Transformation läuft in einem QThread, damit die UI nicht blockiert.
"""

import json
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QLabel, QFileDialog, QMessageBox, QMenu, QTextBrowser, QStackedWidget,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut

# Shortcuts für "Links anspringen" – F3 bleibt primär, weitere als Alternativen
_JUMP_SHORTCUTS = ["F3", "Ctrl+Return", "Ctrl+Space"]

from ui.xml_tree import XmlTreeWidget

# Einstellungsdatei im Aufruf-Verzeichnis (Dot-File → in Dateimanagern versteckt)
_PREFS_FILE = Path.cwd() / ".baumlupe_prefs.json"
_MAX_RECENT = 10

# Platzhalter-Eintrag in der Stylesheet-Auswahl (keine echte Datei dahinter)
_NO_XSL_LABEL = "— Stylesheet wählen —"

# Eingebautes Default-Stylesheet: wird angezeigt solange in einer Pane kein
# echtes XSL gewählt ist. Erzeugt einen Hinweistext statt einer leeren Pane.
_DEFAULT_HINT_XSL = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
  <xsl:output method="xml" indent="yes" encoding="UTF-8"/>
  <xsl:template match="/">
    <Hinweis>
      <Titel>Kein Stylesheet ausgewählt</Titel>
      <Schritt>Oben in der Liste „Stylesheet:“ ein XSL auswählen.</Schritt>
      <Schritt>Oder auf „Durchsuchen…“ klicken, um eine eigene XSL-Datei zu laden.</Schritt>
    </Hinweis>
  </xsl:template>
</xsl:stylesheet>
"""


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

    def __init__(self, xml_path: str | None, xsl_path: str | None = None,
                 xsl_text: str | None = None):
        super().__init__()
        self._xml_path = xml_path
        self._xsl_path = xsl_path
        self._xsl_text = xsl_text

    def run(self) -> None:
        try:
            from saxonche import PySaxonProcessor
            with PySaxonProcessor(license=False) as proc:
                xslt = proc.new_xslt30_processor()
                if self._xsl_text is not None:
                    exe = xslt.compile_stylesheet(stylesheet_text=self._xsl_text)
                else:
                    exe = xslt.compile_stylesheet(stylesheet_file=self._xsl_path)
                # Default-Hinweis braucht kein echtes Quelldokument → Dummy
                if self._xml_path:
                    doc = proc.parse_xml(xml_file_name=self._xml_path)
                else:
                    doc = proc.parse_xml(xml_text="<_/>")
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

        # Ergebnis: XML-Tree oder HTML/Text-Fallback – je nach Ausgabeformat
        self._stack = QStackedWidget()

        self._tree = XmlTreeWidget()
        self._stack.addWidget(self._tree)   # Index 0: XML-Tree

        self._html_view = QTextBrowser()
        self._html_view.setOpenLinks(False)
        self._stack.addWidget(self._html_view)  # Index 1: HTML/Text-Fallback

        layout.addWidget(self._stack)

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
        # Während des Befüllens keine (mehrfachen) Auto-Transforms auslösen
        self._combo.blockSignals(True)
        self._combo.clear()
        stylesheets_dir = Path(self._stylesheets_dir).resolve()

        # Platzhalter: keine Auswahl → Default-Hinweis wird angezeigt
        self._combo.addItem(_NO_XSL_LABEL, None)

        # Zuletzt verwendete externe Dateien zuerst (nicht im stylesheets-Verzeichnis)
        for path in self._recent:
            if Path(path).resolve().parent != stylesheets_dir:
                self._combo.addItem(f"\u2605 {Path(path).name}", path)

        # Dateien aus dem stylesheets-Verzeichnis
        for f in sorted(stylesheets_dir.glob("*.xsl")):
            self._combo.addItem(f.name, str(f))

        # Zuletzt verwendetes Stylesheet vorauswählen, sonst Platzhalter (Index 0)
        if self._recent:
            idx = self._combo.findData(self._recent[0])
            if idx >= 0:
                self._combo.setCurrentIndex(idx)

        self._combo.blockSignals(False)
        # Einmalig den passenden Zustand herstellen (Hinweis oder Transformation)
        self._auto_transform()

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
        """Reagiert auf Stylesheet-/XML-Wechsel.

        Ohne Stylesheet-Auswahl wird der Default-Hinweis angezeigt; mit Auswahl
        wird transformiert, sobald auch eine XML-Datei vorhanden ist.
        """
        if not self._combo.currentData():
            self._show_hint()
        elif self._xml_path:
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
        xsl_path = self._combo.currentData()
        if not xsl_path:
            # Kein Stylesheet gewählt → Default-Hinweis statt leerer Pane
            self._show_hint()
            return
        if not self._xml_path:
            QMessageBox.information(self, "Keine XML-Datei",
                                    "Bitte zuerst eine XML-Datei öffnen.")
            return
        self._start_worker(xsl_path=xsl_path, current_xsl=xsl_path)

    def _show_hint(self) -> None:
        """Default-Stylesheet ausführen: zeigt einen Hinweis statt leerer Pane."""
        self._start_worker(xsl_text=_DEFAULT_HINT_XSL, current_xsl=None)

    def _start_worker(self, *, xsl_path: str | None = None,
                      xsl_text: str | None = None,
                      current_xsl: str | None) -> None:
        """Startet einen TransformWorker und verdrängt einen evtl. laufenden."""
        self._btn_transform.setEnabled(False)
        self._tree.clear()
        self._html_view.clear()

        # Laufenden Worker abbrechen
        if self._worker and self._worker.isRunning():
            self._worker.result_ready.disconnect()
            self._worker.error.disconnect()
            self._worker.quit()
            self._worker.wait()

        self._current_xsl = current_xsl
        self._worker = TransformWorker(self._xml_path, xsl_path=xsl_path,
                                       xsl_text=xsl_text)
        self._worker.result_ready.connect(self._on_result)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_result(self, result: str) -> None:
        self._btn_transform.setEnabled(True)
        if self._current_xsl:
            self._add_to_recent(self._current_xsl)

        # Erst als XML versuchen; bei Parse-Fehler auf HTML/Text-Ansicht zurückfallen
        import xml.etree.ElementTree as _ET
        try:
            _ET.fromstring(result.encode())
            is_xml = True
        except _ET.ParseError:
            is_xml = False

        if is_xml:
            tmp = tempfile.NamedTemporaryFile(suffix=".xml", delete=False,
                                              mode="w", encoding="utf-8")
            tmp.write(result)
            tmp.close()
            self._tmp_path = tmp.name
            self._tree.load_xml(tmp.name)
            self._stack.setCurrentIndex(0)
        else:
            self._html_view.setHtml(result)
            self._stack.setCurrentIndex(1)

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
