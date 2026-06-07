"""XML Tree-View Widget – zeigt eine XML-Datei als aufklappbaren Baum.

Drei Spalten: Elementname | Textwert | Attribute
Stil (Farben, Schriften) wird aus QSettings geladen und kann
zur Laufzeit via apply_style_config() geändert werden.
"""

import copy
import json as _json
from pathlib import Path

from PySide6.QtWidgets import (QTreeWidget, QTreeWidgetItem, QApplication, QMenu,
                                QHBoxLayout, QLineEdit, QPushButton, QLabel,
                                QFrame, QAbstractItemView, QCheckBox)
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
    s = QSettings("BaumLupe", "BaumLupe")
    return {
        key: _coerce(s.value(f"styles/{key}", default), default)
        for key, default in STYLE_DEFAULTS.items()
    }


def save_style_config(config: dict) -> None:
    """Schreibt Stil-Einstellungen in QSettings."""
    s = QSettings("BaumLupe", "BaumLupe")
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
# Suchleiste (intern)
# ---------------------------------------------------------------------------

class _SearchInput(QLineEdit):
    """QLineEdit das Enter/Shift+Enter/Escape/↑↓ an Callbacks weiterleitet."""

    def __init__(self, on_next, on_prev, on_escape, parent=None):
        super().__init__(parent)
        self._on_next   = on_next
        self._on_prev   = on_prev
        self._on_escape = on_escape

    def keyPressEvent(self, event: QKeyEvent) -> None:
        k = event.key()
        if k == Qt.Key.Key_Escape:
            self._on_escape()
            return
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self._on_prev()
            else:
                self._on_next()
            return
        if k == Qt.Key.Key_Down:
            self._on_next()
            return
        if k == Qt.Key.Key_Up:
            self._on_prev()
            return
        super().keyPressEvent(event)


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

        # Suche
        self._search_matches: list[QTreeWidgetItem] = []
        self._search_idx: int = -1
        self._search_bar = self._create_search_bar()
        self._search_bar.setParent(self)
        self._search_bar.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space:
            item = self.currentItem()
            if item and item.childCount() > 0:
                item.setExpanded(not item.isExpanded())
                return
        mods = event.modifiers()
        ctrl       = Qt.KeyboardModifier.ControlModifier
        ctrl_shift = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ctrl_alt   = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        if event.key() == Qt.Key.Key_C:
            if mods == ctrl:
                self.copy_selected()
                return
            if mods == ctrl_shift:
                self.copy_value()
                return
            if mods == ctrl_alt:
                self.copy_attrs()
                return
        if event.key() == Qt.Key.Key_F and mods == ctrl:
            self.show_search()
            return
        super().keyPressEvent(event)

    def contextMenuEvent(self, event) -> None:
        item = self.itemAt(self.viewport().mapFromGlobal(event.globalPos()))
        if item is None:
            return
        self.setCurrentItem(item)
        element = item.data(_COL_ELEMENT, Qt.ItemDataRole.UserRole)
        has_value = bool(element is not None and (element.text or "").strip())
        has_attrs = bool(element is not None and
                         any(k != "xmlview-src-idx" for k in element.attrib))
        menu = QMenu(self)
        act_xml = menu.addAction("XML kopieren        (Ctrl+C)")
        act_xml.triggered.connect(self.copy_selected)
        act_val = menu.addAction("Wert kopieren       (Ctrl+Shift+C)")
        act_val.setEnabled(has_value)
        act_val.triggered.connect(self.copy_value)
        act_attr = menu.addAction("Attribute kopieren  (Ctrl+Alt+C)")
        act_attr.setEnabled(has_attrs)
        act_attr.triggered.connect(self.copy_attrs)
        menu.exec(event.globalPos())

    def _current_element(self):
        item = self.currentItem()
        if item is None:
            return None
        return item.data(_COL_ELEMENT, Qt.ItemDataRole.UserRole)

    def copy_selected(self) -> None:
        """Kopiert den selektierten Knoten + Subtree als XML in die Zwischenablage."""
        element = self._current_element()
        if element is None:
            return
        el = copy.deepcopy(element)
        for node in el.iter():
            node.attrib.pop("xmlview-src-idx", None)
        ET.indent(el, space="  ")
        QApplication.clipboard().setText(ET.tostring(el, encoding="unicode"))

    def copy_value(self) -> None:
        """Kopiert den Textwert des selektierten Elements in die Zwischenablage."""
        element = self._current_element()
        if element is None:
            return
        QApplication.clipboard().setText((element.text or "").strip())

    def copy_attrs(self) -> None:
        """Kopiert die Attribute des selektierten Elements als key=\"value\"-Paare."""
        element = self._current_element()
        if element is None:
            return
        text = "  ".join(f'{k}="{v}"' for k, v in element.attrib.items()
                         if k != "xmlview-src-idx")
        QApplication.clipboard().setText(text)

    # ------------------------------------------------------------------
    # Suche
    # ------------------------------------------------------------------

    def _create_search_bar(self) -> QFrame:
        bar = QFrame(self)
        bar.setFrameShape(QFrame.Shape.StyledPanel)
        bar.setStyleSheet(
            "QFrame { background: palette(window); border: none; "
            "border-top: 1px solid palette(mid); }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        self._search_input = _SearchInput(
            on_next=lambda: self._search_navigate(+1),
            on_prev=lambda: self._search_navigate(-1),
            on_escape=self.hide_search,
        )
        self._search_input.setPlaceholderText("Suchen…")
        self._search_input.setMinimumWidth(160)
        self._search_input.textChanged.connect(self._do_search)
        layout.addWidget(self._search_input)

        self._search_label = QLabel("–")
        self._search_label.setMinimumWidth(42)
        layout.addWidget(self._search_label)

        btn_prev = QPushButton("▲")
        btn_prev.setFixedSize(24, 24)
        btn_prev.setToolTip("Vorheriger Treffer  (Shift+Enter)")
        btn_prev.clicked.connect(lambda: self._search_navigate(-1))
        layout.addWidget(btn_prev)

        btn_next = QPushButton("▼")
        btn_next.setFixedSize(24, 24)
        btn_next.setToolTip("Nächster Treffer  (Enter)")
        btn_next.clicked.connect(lambda: self._search_navigate(+1))
        layout.addWidget(btn_next)

        layout.addSpacing(6)

        self._chk_element = QCheckBox("Element")
        self._chk_element.setChecked(True)
        self._chk_element.toggled.connect(self._do_search)
        layout.addWidget(self._chk_element)

        self._chk_value = QCheckBox("Wert")
        self._chk_value.setChecked(True)
        self._chk_value.toggled.connect(self._do_search)
        layout.addWidget(self._chk_value)

        self._chk_attrs = QCheckBox("Attribute")
        self._chk_attrs.setChecked(True)
        self._chk_attrs.toggled.connect(self._do_search)
        layout.addWidget(self._chk_attrs)

        layout.addSpacing(4)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setToolTip("Suche schließen  (Escape)")
        btn_close.clicked.connect(self.hide_search)
        layout.addWidget(btn_close)

        return bar

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._search_bar.isHidden():
            self._reposition_search_bar()

    def _reposition_search_bar(self) -> None:
        h = self._search_bar.sizeHint().height()
        self._search_bar.setGeometry(0, self.height() - h, self.width(), h)

    def show_search(self) -> None:
        self._reposition_search_bar()
        self._search_bar.show()
        self._search_bar.raise_()
        self._search_input.setFocus()
        self._search_input.selectAll()

    def hide_search(self) -> None:
        self._search_bar.hide()
        self._search_matches = []
        self._search_idx = -1
        self.setFocus()

    def _all_items(self) -> list[QTreeWidgetItem]:
        items: list[QTreeWidgetItem] = []
        def _walk(parent: QTreeWidgetItem) -> None:
            for i in range(parent.childCount()):
                child = parent.child(i)
                items.append(child)
                _walk(child)
        _walk(self.invisibleRootItem())
        return items

    def _item_matches(self, item: QTreeWidgetItem, text: str) -> bool:
        if self._chk_element.isChecked() and text in item.text(_COL_ELEMENT).lower():
            return True
        if self._chk_value.isChecked()   and text in item.text(_COL_VALUE).lower():
            return True
        if self._chk_attrs.isChecked()   and text in item.text(_COL_ATTRS).lower():
            return True
        return False

    def _do_search(self) -> None:
        text = self._search_input.text().lower()
        if not text:
            self._search_matches = []
            self._search_idx = -1
            self._search_label.setText("–")
            self._search_input.setStyleSheet("")
            return

        self._search_matches = [it for it in self._all_items()
                                 if self._item_matches(it, text)]

        if not self._search_matches:
            self._search_idx = -1
            self._search_label.setText("0/0")
            self._search_input.setStyleSheet("background: #ffcccc;")
            return

        self._search_input.setStyleSheet("")
        current = self.currentItem()
        if current in self._search_matches:
            self._search_idx = self._search_matches.index(current)
        else:
            self._search_idx = 0
        self._goto_match(self._search_idx)

    def _search_navigate(self, direction: int) -> None:
        if not self._search_matches:
            return
        self._search_idx = (self._search_idx + direction) % len(self._search_matches)
        self._goto_match(self._search_idx)

    def _goto_match(self, idx: int) -> None:
        item = self._search_matches[idx]
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.setCurrentItem(item)
        self.scrollToItem(item, QAbstractItemView.ScrollHint.PositionAtCenter)
        self._search_label.setText(f"{idx + 1}/{len(self._search_matches)}")

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

    def load_json(self, path: str) -> None:
        """Parst eine JSON-Datei und füllt den Tree."""
        self.clear()
        self._src_idx_to_item = {}
        self._current_path = path

        try:
            with open(path, encoding="utf-8") as fh:
                data = _json.load(fh)
        except (OSError, _json.JSONDecodeError) as exc:
            QTreeWidgetItem(self, [f"Parse-Fehler: {exc}"])
            return

        counter = [0]  # veränderlicher Zähler für rekursive Funktion

        def _add(parent, key: str, value):
            idx = counter[0]
            counter[0] += 1

            item = QTreeWidgetItem(parent)
            item.setData(_COL_ELEMENT, Qt.ItemDataRole.UserRole + 1, idx)

            if isinstance(value, dict):
                item.setText(_COL_ELEMENT, f"{{{key}}}" if key else "{}")
                item.setText(_COL_VALUE, f"{len(value)} Einträge")
                _apply_style(item, self._style)
                self._src_idx_to_item[idx] = item
                for k, v in value.items():
                    _add(item, k, v)
            elif isinstance(value, list):
                item.setText(_COL_ELEMENT, f"[{key}]" if key else "[]")
                item.setText(_COL_VALUE, f"{len(value)} Elemente")
                _apply_style(item, self._style)
                self._src_idx_to_item[idx] = item
                for i, v in enumerate(value):
                    _add(item, str(i), v)
            else:
                item.setText(_COL_ELEMENT, key)
                item.setText(_COL_VALUE, "" if value is None else str(value))
                item.setText(_COL_ATTRS, type(value).__name__ if value is not None else "null")
                _apply_style(item, self._style)
                self._src_idx_to_item[idx] = item

        _add(self, Path(path).name, data)
        self.expandToDepth(2)

    def find_by_json_idx(self, idx: int) -> QTreeWidgetItem | None:
        """Gibt das Tree-Item zum gegebenen JSON-Knoten-Index zurück."""
        return self._src_idx_to_item.get(idx)
