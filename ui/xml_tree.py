"""XML Tree-View Widget – zeigt eine XML-Datei als aufklappbaren Baum."""

from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
import xml.etree.ElementTree as ET


def _namespace_local(tag: str) -> str:
    """Gibt den lokalen Namen ohne Namespace-URI zurück."""
    return tag.split("}")[-1] if "}" in tag else tag


def _build_tree(parent_item: QTreeWidgetItem, element: ET.Element) -> None:
    """Rekursiv Kindelemente als TreeWidgetItems einfügen."""
    for child in element:
        label = _namespace_local(child.tag)

        # Attribut-Kurzvorschau im Label; Textinhalt direkt inline anfügen
        attrs = " ".join(f'{k}="{v}"' for k, v in child.attrib.items())
        text = (child.text or "").strip()
        display = f"<{label}" + (f" {attrs}" if attrs else "") + ">" + text

        item = QTreeWidgetItem(parent_item, [display])
        item.setData(0, Qt.ItemDataRole.UserRole, child)

        _build_tree(item, child)


class XmlTreeWidget(QTreeWidget):
    """Ein QTreeWidget spezialisiert auf XML-Darstellung."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["XML-Struktur"])
        self.setColumnCount(1)
        self.setAlternatingRowColors(True)
        self._current_path: str | None = None

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
            error_item = QTreeWidgetItem(self, [f"Parse-Fehler: {exc}"])
            return

        root = tree.getroot()
        label = _namespace_local(root.tag)
        attrs = " ".join(f'{k}="{v}"' for k, v in root.attrib.items())
        display = f"<{label}" + (f" {attrs}" if attrs else "") + ">"

        root_item = QTreeWidgetItem(self, [display])
        root_item.setData(0, Qt.ItemDataRole.UserRole, root)

        _build_tree(root_item, root)
        self.expandToDepth(2)
