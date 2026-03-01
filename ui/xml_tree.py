"""XML Tree-View Widget – zeigt eine XML-Datei als aufklappbaren Baum.

Drei Spalten: Elementname | Textwert | Attribute
Jede Spalte hat eigene Farb- und Schriftgebung.
"""

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QKeyEvent, QPainter, QPixmap
import xml.etree.ElementTree as ET

# ==============================================================================
# STYLE-KONFIGURATION – hier Farben, Schriften und Spaltenbreiten anpassen
# ==============================================================================

# Farben (CSS-Hex-Werte)
COLOR_ELEMENT = "#1565C0"   # Blau       – Elementname
COLOR_VALUE   = "#2E7D32"   # Grün       – Textwert
COLOR_ATTR    = "#BF360C"   # Rot-Orange – Attribute

# Schrift: Elementname
FONT_ELEMENT_BOLD   = True
FONT_ELEMENT_ITALIC = False
FONT_ELEMENT_SIZE_DELTA = 0   # relativ zur System-Schriftgröße (z.B. +1, -1, 0)

# Schrift: Textwert
FONT_VALUE_BOLD   = False
FONT_VALUE_ITALIC = False
FONT_VALUE_SIZE_DELTA = 0

# Schrift: Attribute
FONT_ATTR_BOLD   = False
FONT_ATTR_ITALIC = True
FONT_ATTR_SIZE_DELTA = -1   # etwas kleiner als der Rest

# Icon: abgerundetes Rechteck in COLOR_ELEMENT (None → kein Icon)
ICON_ELEMENT_ENABLED = True

# Initiale Spaltenbreiten in Pixeln (letzte Spalte dehnt sich automatisch)
COL_WIDTH_ELEMENT = 200
COL_WIDTH_VALUE   = 240

# ==============================================================================

_COL_ELEMENT = 0
_COL_VALUE   = 1
_COL_ATTRS   = 2


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
    """Hält wiederverwendbare Styling-Objekte (muss nach QApplication-Start erzeugt werden)."""

    def __init__(self):
        self.font_element = _make_font(FONT_ELEMENT_BOLD, FONT_ELEMENT_ITALIC, FONT_ELEMENT_SIZE_DELTA)
        self.font_value   = _make_font(FONT_VALUE_BOLD,   FONT_VALUE_ITALIC,   FONT_VALUE_SIZE_DELTA)
        self.font_attr    = _make_font(FONT_ATTR_BOLD,    FONT_ATTR_ITALIC,    FONT_ATTR_SIZE_DELTA)

        self.brush_element = QBrush(QColor(COLOR_ELEMENT))
        self.brush_value   = QBrush(QColor(COLOR_VALUE))
        self.brush_attr    = QBrush(QColor(COLOR_ATTR))

        self.icon_element = _make_icon(QColor(COLOR_ELEMENT)) if ICON_ELEMENT_ENABLED else QIcon()


def _apply_style(item: QTreeWidgetItem, style: _TreeStyle) -> None:
    item.setForeground(_COL_ELEMENT, style.brush_element)
    item.setForeground(_COL_VALUE,   style.brush_value)
    item.setForeground(_COL_ATTRS,   style.brush_attr)
    item.setFont(_COL_ELEMENT, style.font_element)
    item.setFont(_COL_VALUE,   style.font_value)
    item.setFont(_COL_ATTRS,   style.font_attr)
    item.setIcon(_COL_ELEMENT, style.icon_element)


def _build_tree(parent_item: QTreeWidgetItem, element: ET.Element,
                style: _TreeStyle) -> None:
    """Rekursiv Kindelemente als dreispaltige TreeWidgetItems einfügen."""
    for child in element:
        label = _namespace_local(child.tag)
        attrs = "  ".join(f'{k}="{v}"' for k, v in child.attrib.items())
        text  = (child.text or "").strip()

        item = QTreeWidgetItem(parent_item)
        item.setText(_COL_ELEMENT, f"<{label}>")
        item.setText(_COL_VALUE,   text)
        item.setText(_COL_ATTRS,   attrs)
        item.setData(_COL_ELEMENT, Qt.ItemDataRole.UserRole, child)
        _apply_style(item, style)

        _build_tree(item, child, style)


class XmlTreeWidget(QTreeWidget):
    """Ein QTreeWidget spezialisiert auf XML-Darstellung (dreispaltig)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(3)
        self.setHeaderLabels(["Element", "Wert", "Attribute"])
        self.setAlternatingRowColors(True)
        self._current_path: str | None = None
        self._style = _TreeStyle()

        self.setColumnWidth(_COL_ELEMENT, COL_WIDTH_ELEMENT)
        self.setColumnWidth(_COL_VALUE,   COL_WIDTH_VALUE)
        self.header().setStretchLastSection(True)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            item = self.currentItem()
            if item and item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
                return
        super().keyPressEvent(event)

    def load_xml(self, path: str) -> None:
        """Parst die XML-Datei und füllt den Tree."""
        self.clear()
        self._current_path = path

        try:
            tree = ET.parse(path)
        except ET.ParseError as exc:
            QTreeWidgetItem(self, [f"Parse-Fehler: {exc}"])
            return

        root = tree.getroot()
        label = _namespace_local(root.tag)
        attrs = "  ".join(f'{k}="{v}"' for k, v in root.attrib.items())
        text  = (root.text or "").strip()

        root_item = QTreeWidgetItem(self)
        root_item.setText(_COL_ELEMENT, f"<{label}>")
        root_item.setText(_COL_VALUE,   text)
        root_item.setText(_COL_ATTRS,   attrs)
        root_item.setData(_COL_ELEMENT, Qt.ItemDataRole.UserRole, root)
        _apply_style(root_item, self._style)

        _build_tree(root_item, root, self._style)
        self.expandToDepth(2)
