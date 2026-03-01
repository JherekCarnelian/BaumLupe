<?xml version="1.0" encoding="UTF-8"?>
<!--
  Extrahiert nur Bestellpositionen (Artikel + Menge) aus bestellungen.xml.

  Ansatz: xsl:mode on-no-match="deep-skip" (XSLT 3.0)
  → Kein Element wird standardmäßig übernommen.
  → Nur explizit gematchte Pfade landen im Ergebnis.
-->
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

  <xsl:output method="xml" indent="yes" encoding="UTF-8"/>
  <xsl:strip-space elements="*"/>

  <!-- Default: alles ignorieren (inkl. aller Nachfahren) -->
  <xsl:mode on-no-match="deep-skip"/>

  <!-- Gewünschte Pfade: flache Kopie + Kinder weiterverarbeiten -->
  <xsl:template match="bestellungen
                      | bestellung
                      | positionen
                      | position
                      | position/artikel
                      | position/menge">
    <xsl:copy>
      <xsl:apply-templates select="@* | node()"/>
    </xsl:copy>
  </xsl:template>

  <!-- Attribute + Textknoten innerhalb erlaubter Elemente übernehmen -->
  <xsl:template match="@* | text()">
    <xsl:copy/>
  </xsl:template>

</xsl:stylesheet>
