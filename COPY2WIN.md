# XML Viewer v10 – Test auf Windows

## Was kopieren?

Folgende Dateien/Verzeichnisse auf den Windows-Rechner übertragen
(z. B. per USB-Stick oder Netzlaufwerk):

```
xmlViewer-dual-pane/
├── main.py
├── requirements.txt
├── ui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── settings_dialog.py
│   ├── transform_tab.py
│   └── xml_tree.py
└── stylesheets/
    ├── bestellungen.xml
    ├── nur_adressen.xsl
    └── (weitere .xsl / .xml nach Bedarf)
```

Die Verzeichnisse `.git`, `build.spec`, `build.sh`, `build.bat`,
`*.md` werden für den Test **nicht** benötigt.

---

## Einmalige Einrichtung auf Windows

### 1. Python installieren (falls noch nicht vorhanden)

→ https://www.python.org/downloads/
Version 3.11 oder neuer, **„Add Python to PATH"** beim Installer ankreuzen.

### 2. Abhängigkeiten installieren

Eingabeaufforderung (`cmd`) oder PowerShell im Projektverzeichnis öffnen:

```bat
python -m pip install -r requirements.txt
```

Das installiert:
- `PySide6` – Qt-UI-Framework
- `saxonche` – XSLT 3.0 Engine (Saxon/C, mit Windows-DLLs)

---

## Starten

```bat
python main.py stylesheets\bestellungen.xml stylesheets\nur_adressen.xsl
```

Ohne Argumente (Datei-Öffnen-Dialog):

```bat
python main.py
```

Mit Fensterposition:

```bat
python main.py stylesheets\bestellungen.xml stylesheets\nur_adressen.xsl --x 100 --y 50
```

---

## Tastaturkürzel (zur Kontrolle)

| Aktion | Kürzel |
|---|---|
| XML-Datei öffnen | Ctrl+O |
| Pane-Fokus wechseln | Tab · Ctrl+Tab · F6 |
| Zum Quellknoten springen | F3 · Ctrl+Return · Ctrl+Space |
| Knoten auf-/zuklappen | Leertaste |
| Kontextmenü rechte Pane | Rechtsklick |
| Tastaturkürzel anzeigen | F1 |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'PySide6'`**
→ `python -m pip install -r requirements.txt` nochmal ausführen

**Fenster erscheint, aber XSLT-Transformation schlägt fehl**
→ Sicherstellen dass `saxonche` korrekt installiert ist:
`python -c "from saxonche import PySaxonProcessor; print('OK')"`

**Schriftarten oder Farben anders als auf Linux**
→ Normal – Qt passt sich dem Windows-System-Theme an
