"""XML Tree-View Widget – zeigt eine XML-Datei als aufklappbaren Baum.

Drei Spalten: Elementname | Textwert | Attribute
Stil (Farben, Schriften) wird aus QSettings geladen und kann
zur Laufzeit via apply_style_config() geändert werden.
"""

import copy

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem, QApplication, QMenu
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QKeyEvent, QPainter, QPixmap
import xml.etree.ElementTree as ET

_COL_ELEMENT = 0
_COL_VALUE   = 1
_COL_ATTRS   = 2

# Standardwerte – gelten wenn QSettings noch keinen Wert enthält
STYLE_DEFAULTS: dict = {
    "color_element":           "#1565C0",
    "color_value":             "#2E7D32",
    "color_attr":              "#BF360C",
    "color_selection_bg":      "#0066CC",
    "color_selection_text":    "#FFFFFF",
    "color_active_border":     "#1565C0",
    "font_element_bold":       True,
    "font_element_italic":     False,
    "font_element_size_delta": 0,
    "font_value_bold":         False,
    "font_value_italic":       False,
    "font_value_size_delta":   0,
    "font_attr_bold":          False,
    "font_attr_italic":        True,
    "font_attr_size_delta":    -1,
    "icon_element_enabled":    True,
    "col_width_element":       200,
    "col_width_value":         240,
}


def _coerce(value, default):
    """Konvertiert QSettings-Rückgabewert sicher in den Typ des Default-Wertes.
    Nötig weil QSettings auf Windows/Linux unterschiedliche Typen zurückgibt.
    """
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")
    if isinstance(default, int):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    return str(value) if value is not None else default


def load_style_config() -> dict:
    """Liest Stil-Einstellungen aus QSettings; fehlende Keys werden mit STYLE_DEFAULTS gefüllt."""
    s = QSettings("xmlviewer", "xmlviewer")
    return {
        key: _coerce(s.value(f"styles/{key}", default), default)
        for key, default in STYLE_DEFAULTS.items()
    }


def save_style_config(config: dict) -> None:
    """Schreibt Stil-Einstellungen in QSettings."""
    s = QSettings("xmlviewer", "xmlviewer")
    for key, value in config.items():
        s.setValue(f"styles/{key}", value)


# ---------------------------------------------------------------------------
# Interne Hilfsklassen / -funktionen
# ---------------------------------------------------------------------------

def _namespace_local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _make_icon(color: QColor) -> QIcon:
    px = QPixmap(14, 14)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QBrush(color))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(1, 2, 12, 10, 3, 3)
    p.end()
    return QIcon(px)


def _make_font(bold: bool, italic: bool, size_delta: int) -> QFont:
    f = QFont()
    f.setBold(bold)
    f.setItalic(italic)
    pt = f.pointSize()
    if pt > 1 and size_delta != 0:
        f.setPointSize(max(1, pt + size_delta))
    return f


class _TreeStyle:
    """Hält wiederverwendbare Styling-Objekte; wird aus config-Dict gebaut."""

    def __init__(self, config: dict):
        def b(key):  return bool(config.get(key, STYLE_DEFAULTS[key]))
        def i(key):  return int(config.get(key, STYLE_DEFAULTS[key]))
        def s(key):  return str(config.get(key, STYLE_DEFAULTS[key]))

        self.font_element = _make_font(b("font_element_bold"), b("font_element_italic"), i("font_element_size_delta"))
        self.font_value   = _make_font(b("font_value_bold"),   b("font_value_italic"),   i("font_value_size_delta"))
        self.font_attr    = _make_font(b("font_attr_bold"),    b("font_attr_italic"),    i("font_attr_size_delta"))

        self.brush_element = QBrush(QColor(s("color_element")))
        self.brush_value   = QBrush(QColor(s("color_value")))
        self.brush_attr    = QBrush(QColor(s("color_attr")))

        self.icon_element = _make_icon(QColor(s("color_element"))) if b("icon_element_enabled") else QIcon()


def _apply_style(item: QTreeWidgetItem, style: _TreeStyle) -> None:
    item.setForeground(_COL_ELEMENT, style.brush_element)
    item.setForeground(_COL_VALUE,   style.brush_value)
    item.setForeground(_COL_ATTRS,   style.brush_attr)
    item.setFont(_COL_ELEMENT, style.font_element)
    item.setFont(_COL_VALUE,   style.font_value)
    item.setFont(_COL_ATTRS,   style.font_attr)
    item.setIcon(_COL_ELEMENT, style.icon_element)


def _build_tree(parent_item: QTreeWidgetItem, element: ET.Element,
                style: _TreeStyle,
                elem_to_idx: dict, idx_to_item: dict) -> None:
    for child in element:
        label = _namespace_local(child.tag)
        # xmlview-src-idx ist internes Navigations-Attribut → nicht anzeigen
        attrs = "  ".join(f'{k}="{v}"' for k, v in child.attrib.items()
                          if k != "xmlview-src-idx")
        text  = (child.text or "").strip()

        item = QTreeWidgetItem(parent_item)
        item.setText(_COL_ELEMENT, f"<{label}>")
        item.setText(_COL_VALUE,   text)
        item.setText(_COL_ATTRS,   attrs)
        item.setData(_COL_ELEMENT, Qt.ItemDataRole.UserRole, child)
        _apply_style(item, style)

        idx_to_item[elem_to_idx[id(child)]] = item
        _build_tree(item, child, style, elem_to_idx, idx_to_item)


# ---------------------------------------------------------------------------
# Öffentliches Widget
# ---------------------------------------------------------------------------

class XmlTreeWidget(QTreeWidget):
    """Ein QTreeWidget spezialisiert auf XML-Darstellung (dreispaltig)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHeaderLabels(["Element", "Wert", "Attribute"])
        self.setAlternatingRowColors(True)
        self._current_path: str | None = None
        self._src_idx_to_item: dict[int, QTreeWidgetItem] = {}

        config = load_style_config()
        self._style_config = config
        self._style = _TreeStyle(config)
        self.setColumnWidth(_COL_ELEMENT, int(config["col_width_element"]))
        self.setColumnWidth(_COL_VALUE,   int(config["col_width_value"]))
        self.header().setStretchLastSection(True)
        self._apply_selection_style(config)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            item = self.currentItem()
            if item and item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
                return
        if (event.key() == Qt.Key.Key_C and
                event.modifiers() == Qt.KeyboardModifier.ControlModifier):
            self.copy_selected()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(self.viewport().mapFromGlobal(event.globalPos()))
        if item is None:
            return
        self.setCurrentItem(item)
        menu = QMenu(self)
        act_copy = menu.addAction("Kopieren  (Ctrl+C)")
        act_copy.triggered.connect(self.copy_selected)
        menu.exec(event.globalPos())

    def copy_selected(self) -> None:
        """Kopiert den selektierten Knoten + Subtree als XML in die Zwischenablage."""
        item = self.currentItem()
        if item is None:
            return
        element = item.data(_COL_ELEMENT, Qt.ItemDataRole.UserRole)
        if element is None:
            return
        el = copy.deepcopy(element)
        # Interne Navigations-Attribute entfernen
        for node in el.iter():
            node.attrib.pop("xmlview-src-idx", None)
        ET.indent(el, space="  ")
        xml_str = ET.tostring(el, encoding="unicode")
        QApplication.clipboard().setText(xml_str)

    def apply_style_config(self, config: dict) -> None:
        """Übernimmt neue Stil-Einstellungen und stylt alle sichtbaren Items neu."""
        self._style = _TreeStyle(config)
        self.setColumnWidth(_COL_ELEMENT, int(config.get("col_width_element", STYLE_DEFAULTS["col_width_element"])))
        self.setColumnWidth(_COL_VALUE,   int(config.get("col_width_value",   STYLE_DEFAULTS["col_width_value"])))
        self._restyle_items(self.invisibleRootItem())
        self._apply_selection_style(config)

    def _apply_selection_style(self, config: dict) -> None:
        self._style_config = config
        bg     = config.get("color_selection_bg",   STYLE_DEFAULTS["color_selection_bg"])
        text   = config.get("color_selection_text", STYLE_DEFAULTS["color_selection_text"])
        border = config.get("color_active_border",  STYLE_DEFAULTS["color_active_border"])
        if self.hasFocus():
            border_css = f"QTreeWidget {{ border: 2px solid {border}; }}"
        else:
            border_css = "QTreeWidget { border: 1px solid #3c3c3c; }"
        self.setStyleSheet(
            border_css
            + f"QTreeWidget::item:selected {{ color: {text}; background: {bg}; }}"
            + f"QTreeWidget::item:selected:!active {{ color: {text}; background: {bg}; }}"
            + "QTreeWidget::item:hover { background: transparent; }"
        )

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        self._apply_selection_style(self._style_config)

    def focusOutEvent(self, event) -> None:
        super().focusOutEvent(event)
        self._apply_selection_style(self._style_config)

    def _restyle_items(self, parent: QTreeWidgetItem) -> None:
        for i in range(parent.childCount()):
            item = parent.child(i)
            _apply_style(item, self._style)
            self._restyle_items(item)

    def find_by_src_idx(self, idx: int) -> QTreeWidgetItem | None:
        """Gibt das Tree-Item zum gegebenen DFS-Index zurück (für Dual-Pane-Navigation)."""
        return self._src_idx_to_item.get(idx)

    def load_xml(self, path: str) -> None:
        """Parst die XML-Datei und füllt den Tree."""
        self.clear()
        self._src_idx_to_item = {}
        self._current_path = path

        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            QTreeWidgetItem(self, [f"Parse-Fehler: {exc}"])
            return

        # DFS-Index-Mapping: id(element) → idx (identisch mit ET.iter()-Reihenfolge)
        elem_to_idx = {id(el): idx for idx, el in enumerate(tree.iter())}

        root = tree.getroot()
        label = _namespace_local(root.tag)
        attrs = "  ".join(f'{k}="{v}"' for k, v in root.attrib.items()
                          if k != "xmlview-src-idx")
        text  = (root.text or "").strip()

        root_item = QTreeWidgetItem(self)
        root_item.setText(_COL_ELEMENT, f"<{label}>")
        root_item.setText(_COL_VALUE,   text)
        root_item.setText(_COL_ATTRS,   attrs)
        root_item.setData(_COL_ELEMENT, Qt.ItemDataRole.UserRole, root)
        _apply_style(root_item, self._style)

        self._src_idx_to_item[elem_to_idx[id(root)]] = root_item
        _build_tree(root_item, root, self._style, elem_to_idx, self._src_idx_to_item)
        self.expandToDepth(2)
