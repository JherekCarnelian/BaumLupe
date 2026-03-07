# Dual-Pane-Verknüpfung: Transform-Ergebnis → XML-Quellknoten

## Ziel

Tastaturkürzel **F3** in der rechten (Transform-)Pane springt zum
entsprechenden Knoten in der linken (XML-Eingabe-)Pane.

## Architektur: Python Pre-Annotation

Python injiziert `data-src-idx` *vor* der XSLT-Transformation in eine
temporäre Kopie der XML-Datei. Die XSLT bekommt eine bereits annotierte
XML und kopiert das Attribut einfach durch – **keine XSLT-Änderung nötig**,
solange das Stylesheet Attribute mit `@*` übernimmt (Standard-Pattern).

```
Original XML          Annotierte Temp-XML        Transform-Ergebnis
──────────────        ───────────────────        ──────────────────
<bestellung           <bestellung                <bestellung
  id="B001">    →       id="B001"          →       id="B001"
  <kunde>               data-src-idx="1">          data-src-idx="1">
    ...                 <kunde                     <kunde
                          data-src-idx="2">          data-src-idx="2">
                          ...                        ...
```

### Ablauf beim XML-Laden

1. `XmlTreeWidget.load_xml(original_path)` → linke Pane aufbauen,
   `_src_idx_to_item`-Dict befüllen (DFS-Index → QTreeWidgetItem)
2. `_create_annotated_xml(original_path)` → temporäre XML-Datei mit
   `data-src-idx` auf allen Elementen
3. `TransformTab.set_xml_path(annotated_path)` → XSLT läuft auf Kopie

### DFS-Index-Formel

```python
# Python (identisch für Original und Kopie):
for idx, el in enumerate(tree.iter()):
    el.set("data-src-idx", str(idx))
```

`ET.ElementTree.iter()` traversiert in Document Order (DFS, Pre-Order).

### Ablauf beim F3-Tastaturkürzel

```
Benutzer drückt F3 in rechter Pane
→ TransformTab._navigate_to_source()
  → liest data-src-idx aus ET.Element des selektierten Items
  → sendet navigate_to_source(idx) Signal
→ MainWindow._on_navigate_to_source(idx)
  → XmlTreeWidget.find_by_src_idx(idx) → QTreeWidgetItem links
  → Vorfahren aufklappen, scrollToItem(PositionAtTop), setCurrentItem
```

## Voraussetzungen für das XSLT

### Kein Änderungsbedarf bei Standard-Pattern

```xml
<xsl:template match="element">
  <xsl:copy>
    <xsl:apply-templates select="@* | node()"/>  ← @* kopiert data-src-idx
  </xsl:copy>
</xsl:template>

<xsl:template match="@* | text()">
  <xsl:copy/>                                    ← kopiert Attribute 1:1
</xsl:template>
```

### Nur bei selbst generierten Elementen nötig

Wenn ein Template ein *neues* Element erzeugt (kein `xsl:copy`), muss
`data-src-idx` explizit übernommen werden:

```xml
<xsl:template match="position">
  <item>
    <!-- Quell-Attribut manuell übertragen: -->
    <xsl:attribute name="data-src-idx" select="@data-src-idx"/>
    <xsl:value-of select="artikel"/>
  </item>
</xsl:template>
```

### Elemente ohne Rücklink

Rein strukturell generierte Wrapper-Elemente (z. B. `<root>`, `<liste>`)
erhalten kein `data-src-idx` → F3 tut für diese Items nichts.
Das ist kein Fehler, sondern erwartetes Verhalten.

## Dateien

| Datei | Zweck |
|---|---|
| `stylesheets/src-link-template.xsl` | Beispiel-Template mit explizitem Rücklink |
| `stylesheets/adressen_linked.xsl` | Ältere Variante (manueller XSLT-Ansatz, veraltet) |
| `stylesheets/nur_adressen.xsl` | Funktioniert **unverändert** dank Pre-Annotation |

## Tastaturkürzel

**F3** – aktiviert wenn die rechte (Transform-)Pane oder eines ihrer
Kind-Widgets den Fokus hat (`WidgetWithChildrenShortcut`).
