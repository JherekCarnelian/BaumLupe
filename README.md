# XML Viewer (saxonche)

Schlanker XML-Viewer mit XSLT 3.0-Unterstützung via saxonche (Saxon/C Python-Bindings).
Keine Node.js-Abhängigkeit.

## Voraussetzungen

```
pip install -r requirements.txt
```

Requirements: `PySide6>=6.7.0`, `saxonche>=12.9.0`

## Starten (Linux)

```bash
chmod +x run.sh
./run.sh
./run.sh stylesheets/bestellungen.xml stylesheets/nur_adressen.xsl
```

## Windows (direkt)

```bat
python main.py
python main.py stylesheets\bestellungen.xml stylesheets\nur_adressen.xsl
```

## Build (PyInstaller)

**Linux:**
```bash
chmod +x build.sh
./build.sh
# Ergebnis: dist/xmlViewer/xmlViewer
```

**Windows:**
```bat
build.bat
rem Ergebnis: dist\xmlViewer\xmlViewer.exe
```

## Architektur

- `saxonche.PySaxonProcessor` führt XSLT 3.0 direkt in Python aus
- Transformation läuft in `QThread` → UI bleibt reaktionsfähig
- Ergebnis wird als XML-Tree dargestellt (bei XML-Output-Stylesheets)
