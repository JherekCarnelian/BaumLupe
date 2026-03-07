<?xml version="1.0" encoding="UTF-8"?>
<!--
  adressen_linked.xsl
  ===================
  Wie nur_adressen.xsl, aber mit xmlview-src-idx auf jedem Output-Element.
  Das Attribut verknüpft jeden Ergebnis-Knoten mit seinem Quellknoten
  in der linken XML-Pane (Dual-Pane-Navigation via F3).

  Formel: count(preceding::*) + count(ancestor::*)
  → ergibt denselben 0-basierten DFS-Index wie ET.ElementTree.iter() in Python.
-->
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:output method="xml" indent="yes" encoding="UTF-8"/>
  <xsl:strip-space elements="*"/>

  <!-- Default: alles ignorieren -->
  <xsl:mode on-no-match="deep-skip"/>

  <!-- Für alle gematchten Elemente: xsl:copy + xmlview-src-idx hinzufügen -->
  <xsl:template match="bestellungen
                      | bestellung
                      | kunde
                      | kunde/name
                      | adresse
                      | adresse/*">
    <xsl:copy>
      <!-- Brücke zum Quellknoten: DFS-Index des aktuellen Quellknotens -->
      <xsl:attribute name="xmlview-src-idx">
        <xsl:value-of select="count(preceding::*) + count(ancestor::*)"/>
      </xsl:attribute>
      <xsl:apply-templates select="@* | node()"/>
    </xsl:copy>
  </xsl:template>

  <!-- Attribute + Textknoten innerhalb erlaubter Elemente übernehmen -->
  <xsl:template match="@* | text()">
    <xsl:copy/>
  </xsl:template>

</xsl:stylesheet>
