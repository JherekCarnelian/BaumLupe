# Build-Optimierung: Größe & Startzeit

Aktueller Stand: ~80 MB, spürbarer Start-Delay (PySide6-Initialisierung).

---

## Option 1: Unused Qt-Module ausschließen (leicht, größter Effekt)

`build.spec` → `excludes`-Liste erweitern:

```python
excludes=[
    'PySide6.QtWebEngine', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
    'PySide6.Qt3DAnimation', 'PySide6.Qt3DCore', 'PySide6.Qt3DExtras',
    'PySide6.Qt3DInput', 'PySide6.Qt3DLogic', 'PySide6.Qt3DRender',
    'PySide6.QtCharts', 'PySide6.QtDataVisualization',
    'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuick3D', 'PySide6.QtQuickWidgets',
    'PySide6.QtSql', 'PySide6.QtBluetooth', 'PySide6.QtNfc',
    'PySide6.QtPositioning', 'PySide6.QtRemoteObjects', 'PySide6.QtSensors',
    'PySide6.QtSerialBus', 'PySide6.QtSerialPort', 'PySide6.QtStateMachine',
    'PySide6.QtTest', 'PySide6.QtTextToSpeech', 'PySide6.QtUiTools',
    'PySide6.QtHelp', 'PySide6.QtDesigner',
],
```

Erwartetes Ergebnis: **~35 MB**

---

## Option 2: PySide6-Essentials statt vollem PySide6

Nur Kern-Module installieren → PyInstaller findet Add-ons gar nicht erst:

```bat
pip uninstall PySide6
pip install PySide6-Essentials
```

`requirements.txt` entsprechend anpassen:
```
PySide6-Essentials>=6.7.0
saxonche>=12.9.0
```

Gut kombinierbar mit Option 1. Erwartetes Ergebnis: **~25 MB**

---

## Option 3: Nuitka statt PyInstaller

Kompiliert Python zu echtem C-Code → deutlich schnellerer Start, oft 30–50 % kleiner.

```bat
pip install nuitka
python -m nuitka --onedir --windows-disable-console --follow-imports main.py
```

Voraussetzungen:
- C-Compiler: MSVC (Visual Studio Build Tools) oder MinGW
- Build dauert länger als PyInstaller

Erwartetes Ergebnis: **~20–30 MB, merklich schnellerer Start**

---

## Vergleichsübersicht

| Option | Aufwand | Größe (ca.) | Startzeit |
|---|---|---|---|
| Aktueller Stand | – | ~80 MB | spürbar |
| Option 1: Qt ausschließen | gering | ~35 MB | etwas besser |
| Option 1+2: Qt + Essentials | gering | ~25 MB | etwas besser |
| Option 3: Nuitka | mittel | ~20–30 MB | deutlich besser |

## Hinweise

- `--onefile` **nicht** verwenden: entpackt sich bei jedem Start in ein Temp-Verzeichnis → langsamerer Start als `--onedir`
- `--onedir` (aktuell) ist für Startzeit die bessere Wahl
- saxonche ist bereits lazy-importiert (nur beim ersten Transform) – das ist schon optimal
