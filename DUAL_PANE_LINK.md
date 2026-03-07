# Dual-Pane-Verknüpfung: Transform-Ergebnis → XML-Quellknoten

## Ziel

Tastaturkürzel in der rechten (Transform-)Pane springt zum
entsprechenden Knoten in der linken (XML-Eingabe-)Pane.

## Grundidee: Dokument-Reihenfolge-Index (`data-src-idx`)

XSLT und Python traversieren einen XML-Baum beide in derselben
Reihenfolge (DFS, Pre-Order). Das ermöglicht eine einfache Brücke:

### XSLT-Seite

Die Formel

```xpath
count(preceding::*) + count(ancestor::*)
```

ergibt für jeden Quellknoten einen eindeutigen, 0-basierten Index –
identisch mit dem Index, den `ET.ElementTree.iter()` in Python vergibt.

Diesen Index schreibt die XSLT als Attribut auf Output-Elemente:

```xml
<xsl:attribute name="data-src-idx">
  <xsl:value-of select="count(preceding::*) + count(ancestor::*)"/>
</xsl:attribute>
```

### Python-Seite (noch zu implementieren)

Beim Laden der XML-Datei links:
- `ET.ElementTree.iter()` liefert alle Elemente in DFS-Reihenfolge
- `enumerate()` ergibt den Index
- Mapping: `_src_idx_to_item: dict[int, QTreeWidgetItem]`

Beim Tastaturkürzel (geplant: **F3**) in der rechten Pane:
1. Ausgewähltes Item im Ergebnis-Tree lesen
2. `data-src-idx`-Attribut (Spalte „Attribute") auslesen
3. Im Mapping `_src_idx_to_item` nachschlagen
4. Linkes Tree-Item anspringen, aufklappen, highlighten

## Voraussetzungen für das XSLT

Damit die Verknüpfung funktioniert, muss das XSLT folgendes leisten:

### 1. `data-src-idx` auf Output-Elementen setzen

Jedes Output-Element, das zu einem Quellknoten zurückverlinken soll,
muss das Attribut `data-src-idx` tragen, berechnet **im Kontext des
Quellknotens** (nicht des Output-Elements):

```xml
<!-- Innerhalb eines xsl:template das auf einen Quellknoten matcht: -->
<output-element>
  <xsl:attribute name="data-src-idx">
    <xsl:value-of select="count(preceding::*) + count(ancestor::*)"/>
  </xsl:attribute>
  <!-- ... weiterer Inhalt ... -->
</output-element>
```

### 2. Nur Quellknoten-Kontext verwenden

Die Formel muss **im Kontext des Quellknotens** ausgewertet werden,
also innerhalb von `<xsl:template match="...">` oder
`<xsl:for-each select="...">` – nicht innerhalb von generierten
Wrapper-Elementen ohne Quelläquivalent.

### 3. Generierte Elemente ohne Quelläquivalent

Elemente, die die XSLT rein strukturell erzeugt (z. B. Wrapper `<div>`,
`<section>`), sollen **kein** `data-src-idx` erhalten. Sie werden vom
Python-Code dann einfach ignoriert.

### 4. Namespaces

`count(preceding::*)` zählt Elemente unabhängig von Namespaces.
Das Mapping funktioniert auch bei Namespace-präfixierten Quell-XMLs
korrekt, solange Python und XSLT denselben DOM traversieren.

## Warum nicht XPath als String?

Alternativ könnte man den XPath-Ausdruck des Quellknotens als String
einbetten (z. B. `/root/orders[1]/order[2]`). Das ist lesbarer, aber:
- XPath-Generierung in XSLT ist aufwändiger (Named Template nötig)
- Python müsste XPath auswerten (ET unterstützt nur eine Teilmenge)
- Der Index-Ansatz ist simpler und robuster

## Geplantes Tastaturkürzel

**F3** – in dieser Anwendung noch nicht belegt, semantisch passend
(„zur Quelle springen").

---

## Beispiel-Workflow

```
Benutzer wählt Element im rechten Pane aus
→ drückt F3
→ Python liest data-src-idx="7" vom Item
→ sucht _src_idx_to_item[7] → QTreeWidgetItem im linken Pane
→ scrollTo(item), setCurrentItem(item), item aufklappen
```
