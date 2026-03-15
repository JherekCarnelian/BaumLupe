"""Stil-Einstellungs-Dialog für den XML-Viewer.

Ermöglicht das Anpassen von Farben, Schriften und Spaltenbreiten mit
Live-Vorschau direkt im Hauptfenster. Einstellungen werden in QSettings
gespeichert (plattformübergreifend: Registry auf Windows, .conf auf Linux).
"""

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
    QLabel, QCheckBox, QSpinBox, QPushButton,
    QVBoxLayout, QHBoxLayout, QColorDialog,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor

from ui.xml_tree import STYLE_DEFAULTS


class _ColorButton(QPushButton):
    """Button der die aktuelle Farbe als Hintergrund zeigt; Klick öffnet QColorDialog."""

    color_changed = Signal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(80, 24)
        self._color = color
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self) -> None:
        c = QColor(self._color)
        lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
        fg = "#000000" if lum > 128 else "#ffffff"
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self._color}; color: {fg}; "
            f"border: 1px solid #888; border-radius: 3px; padding: 0 4px; }}"
        )
        self.setText(self._color.upper())

    def _pick(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self, "Farbe wählen")
        if color.isValid():
            self._color = color.name()
            self._refresh()
            self.color_changed.emit(self._color)

    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        self._color = color
        self._refresh()


class SettingsDialog(QDialog):
    """Dialog zum Anpassen von Schriften, Farben und Spaltenbreiten mit Live-Vorschau."""

    def __init__(self, current_config: dict, on_preview, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stil-Einstellungen")
        self.setMinimumWidth(540)
        self._config = dict(current_config)
        self._on_preview = on_preview
        self._build_ui()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # --- Schriften & Farben ---
        font_group = QGroupBox("Schriften && Farben")
        grid = QGridLayout(font_group)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        for col, text in enumerate(["", "Farbe", "Fett", "Kursiv", "Größe (±pt)", ""], 0):
            lbl = QLabel(text)
            lbl.setStyleSheet("font-weight: bold;")
            grid.addWidget(lbl, 0, col)

        # (anzeigetext, config-prefix, icon-checkbox zeigen?)
        rows = [
            ("Elementname", "element", True),
            ("Textwert",    "value",   False),
            ("Attribute",   "attr",    False),
        ]

        self._widgets: dict[str, dict] = {}

        for row_idx, (label, prefix, show_icon) in enumerate(rows, 1):
            grid.addWidget(QLabel(label + ":"), row_idx, 0)

            btn_color = _ColorButton(str(self._config[f"color_{prefix}"]))
            btn_color.color_changed.connect(lambda c, p=prefix: self._on_color(p, c))
            grid.addWidget(btn_color, row_idx, 1)

            chk_bold = QCheckBox()
            chk_bold.setChecked(bool(self._config[f"font_{prefix}_bold"]))
            chk_bold.stateChanged.connect(lambda _s, p=prefix: self._on_font(p))
            grid.addWidget(chk_bold, row_idx, 2)

            chk_italic = QCheckBox()
            chk_italic.setChecked(bool(self._config[f"font_{prefix}_italic"]))
            chk_italic.stateChanged.connect(lambda _s, p=prefix: self._on_font(p))
            grid.addWidget(chk_italic, row_idx, 3)

            spin_size = QSpinBox()
            spin_size.setRange(-5, 10)
            spin_size.setValue(int(self._config[f"font_{prefix}_size_delta"]))
            spin_size.setFixedWidth(56)
            spin_size.valueChanged.connect(lambda _v, p=prefix: self._on_font(p))
            grid.addWidget(spin_size, row_idx, 4)

            self._widgets[prefix] = {
                "color": btn_color, "bold": chk_bold,
                "italic": chk_italic, "size": spin_size,
            }

            if show_icon:
                self._chk_icon = QCheckBox("Icon")
                self._chk_icon.setChecked(bool(self._config["icon_element_enabled"]))
                self._chk_icon.stateChanged.connect(self._on_icon)
                grid.addWidget(self._chk_icon, row_idx, 5)

        layout.addWidget(font_group)

        # --- Selektion ---
        sel_group = QGroupBox("Selektion")
        sel_layout = QHBoxLayout(sel_group)

        sel_layout.addWidget(QLabel("Hintergrund:"))
        self._btn_sel_bg = _ColorButton(str(self._config["color_selection_bg"]))
        self._btn_sel_bg.color_changed.connect(lambda c: self._on_sel_color("color_selection_bg", c))
        sel_layout.addWidget(self._btn_sel_bg)

        sel_layout.addSpacing(24)

        sel_layout.addWidget(QLabel("Text:"))
        self._btn_sel_text = _ColorButton(str(self._config["color_selection_text"]))
        self._btn_sel_text.color_changed.connect(lambda c: self._on_sel_color("color_selection_text", c))
        sel_layout.addWidget(self._btn_sel_text)

        sel_layout.addSpacing(24)

        sel_layout.addWidget(QLabel("Aktive Pane:"))
        self._btn_active_border = _ColorButton(str(self._config["color_active_border"]))
        self._btn_active_border.color_changed.connect(lambda c: self._on_sel_color("color_active_border", c))
        sel_layout.addWidget(self._btn_active_border)

        sel_layout.addStretch()
        layout.addWidget(sel_group)

        # --- Spaltenbreiten ---
        width_group = QGroupBox("Spaltenbreiten (Pixel)")
        width_layout = QHBoxLayout(width_group)

        width_layout.addWidget(QLabel("Element:"))
        self._spin_col_element = QSpinBox()
        self._spin_col_element.setRange(60, 800)
        self._spin_col_element.setValue(int(self._config["col_width_element"]))
        self._spin_col_element.valueChanged.connect(self._on_col_width)
        width_layout.addWidget(self._spin_col_element)

        width_layout.addSpacing(24)
        width_layout.addWidget(QLabel("Wert:"))
        self._spin_col_value = QSpinBox()
        self._spin_col_value.setRange(60, 800)
        self._spin_col_value.setValue(int(self._config["col_width_value"]))
        self._spin_col_value.valueChanged.connect(self._on_col_width)
        width_layout.addWidget(self._spin_col_value)
        width_layout.addStretch()

        layout.addWidget(width_group)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Zurücksetzen")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_row.addWidget(buttons)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Change-Handler → live preview
    # ------------------------------------------------------------------

    def _on_color(self, prefix: str, color: str) -> None:
        self._config[f"color_{prefix}"] = color
        self._on_preview(self._config)

    def _on_sel_color(self, key: str, color: str) -> None:
        self._config[key] = color
        self._on_preview(self._config)

    def _on_font(self, prefix: str) -> None:
        w = self._widgets[prefix]
        self._config[f"font_{prefix}_bold"]       = w["bold"].isChecked()
        self._config[f"font_{prefix}_italic"]     = w["italic"].isChecked()
        self._config[f"font_{prefix}_size_delta"] = w["size"].value()
        self._on_preview(self._config)

    def _on_icon(self) -> None:
        self._config["icon_element_enabled"] = self._chk_icon.isChecked()
        self._on_preview(self._config)

    def _on_col_width(self) -> None:
        self._config["col_width_element"] = self._spin_col_element.value()
        self._config["col_width_value"]   = self._spin_col_value.value()
        self._on_preview(self._config)

    # ------------------------------------------------------------------
    # Reset & Ergebnis
    # ------------------------------------------------------------------

    def _reset_defaults(self) -> None:
        """Setzt alle Widgets auf STYLE_DEFAULTS zurück, ohne Zwischenzustände zu previewen."""
        self._config = dict(STYLE_DEFAULTS)

        # Widgets stumm aktualisieren
        for prefix, ws in self._widgets.items():
            ws["color"].set_color(str(self._config[f"color_{prefix}"]))
            for w in (ws["bold"], ws["italic"], ws["size"]):
                w.blockSignals(True)
            ws["bold"].setChecked(bool(self._config[f"font_{prefix}_bold"]))
            ws["italic"].setChecked(bool(self._config[f"font_{prefix}_italic"]))
            ws["size"].setValue(int(self._config[f"font_{prefix}_size_delta"]))
            for w in (ws["bold"], ws["italic"], ws["size"]):
                w.blockSignals(False)

        for w in (self._chk_icon, self._spin_col_element, self._spin_col_value):
            w.blockSignals(True)
        self._chk_icon.setChecked(bool(self._config["icon_element_enabled"]))
        self._spin_col_element.setValue(int(self._config["col_width_element"]))
        self._spin_col_value.setValue(int(self._config["col_width_value"]))
        for w in (self._chk_icon, self._spin_col_element, self._spin_col_value):
            w.blockSignals(False)

        self._btn_sel_bg.set_color(str(self._config["color_selection_bg"]))
        self._btn_sel_text.set_color(str(self._config["color_selection_text"]))
        self._btn_active_border.set_color(str(self._config["color_active_border"]))

        self._on_preview(self._config)

    def get_config(self) -> dict:
        return dict(self._config)
