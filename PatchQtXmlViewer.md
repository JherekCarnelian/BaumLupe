# Patch: QSplitter-Kollaps-Bug in main_window.py

## Problem
Der Haupt-Splitter (links XML-Tree / rechts Transform-Panes) konnte durch
Doppelklick auf den Splitter-Griff kollabiert werden. Der kollabierte Zustand
wurde in QSettings gespeichert und beim nächsten Start wiederhergestellt,
sodass eine Fensterhälfte unsichtbar blieb.

## Ursache
`_col_splitter` hatte bereits `setChildrenCollapsible(False)`, dem Haupt-
Splitter `self._splitter` fehlte diese Zeile. Außerdem gab es keine Absicherung
in `_restore_geometry`, die einen gespeicherten Kollaps-Zustand korrigiert.

---

## Änderung 1 — `_setup_ui()`: Kollabieren des Haupt-Splitters verhindern

**Datei:** `main_window.py`  
**Methode:** `_setup_ui`  
**Stelle:** direkt nach der Zeile `self._splitter = QSplitter(Qt.Orientation.Horizontal)`

### Vorher
```python
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Linke Seite: XML-Eingabe ---
```

### Nachher
```python
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)

        # --- Linke Seite: XML-Eingabe ---
```

---

## Änderung 2 — `_restore_geometry()`: Kaputten gespeicherten Zustand abfangen

**Datei:** `main_window.py`  
**Methode:** `_restore_geometry`  
**Stelle:** im Block, der `splitter_multi_h_last` wiederherstellt

### Vorher
```python
        splitter_state = _SHARED_SETTINGS.value("splitter_multi_h_last")
        if splitter_state:
            self._splitter.restoreState(splitter_state)
```

### Nachher
```python
        splitter_state = _SHARED_SETTINGS.value("splitter_multi_h_last")
        if splitter_state:
            self._splitter.restoreState(splitter_state)
            if 0 in self._splitter.sizes():
                self._splitter.setSizes([500, 900])
```

---

## Hinweis für die Anwendung

Beide Änderungen sind rein additiv (je eine neue Zeile). Nach dem Patch kann
ein `diff` gegen das Original genau diese zwei Stellen zeigen und sonst keine
weiteren Abweichungen.

Falls die QSettings auf dem Zielrechner bereits einen kollabierten Zustand
enthalten, greift Änderung 2 beim nächsten Start automatisch. Ein manuelles
Löschen des Registry-Schlüssels ist danach nicht mehr nötig.

**Windows-Registry-Pfad** (nur zur Info, nicht mehr erforderlich):  
`HKEY_CURRENT_USER\Software\xmlviewer\xmlviewer`
