<?xml version="1.0" encoding="UTF-8"?>
<!--
  src-link-template.xsl
  =====================
  Vorlage für XSLT-Stylesheets, die die Dual-Pane-Navigation unterstützen.

  ANFORDERUNG: Jedes Output-Element, das zu einem Quellknoten zurückverlinken
  soll, muss das Attribut data-src-idx tragen.

  Formel (im Kontext des Quellknotens):
    count(preceding::*) + count(ancestor::*)

  Dieses Template zeigt drei typische Einsatzmuster:

    1. Identity-Transform (alle Elemente 1:1 mit Link)
    2. Selektive Ausgabe (nur bestimmte Elemente mit Link)
    3. Generierte Wrapper ohne Link

  Passe das für dein konkretes Stylesheet an.
-->
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  expand-text="yes">

  <xsl:output method="xml" indent="yes" encoding="UTF-8"/>

  <!-- ============================================================
       MUSTER 1: Identity-Transform
       Alle Quellknoten werden 1:1 kopiert und erhalten data-src-idx.
       Gut als Ausgangspunkt zum Weiterentwickeln.
       ============================================================ -->

  <!--
  <xsl:template match="*">
    <xsl:copy>
      <xsl:attribute name="data-src-idx">
        <xsl:value-of select="count(preceding::*) + count(ancestor::*)"/>
      </xsl:attribute>
      <xsl:apply-templates select="@* | node()"/>
    </xsl:copy>
  </xsl:template>

  <xsl:template match="@* | text() | comment() | processing-instruction()">
    <xsl:copy/>
  </xsl:template>
  -->


  <!-- ============================================================
       MUSTER 2: Selektive Ausgabe mit Link
       Nur bestimmte Quellknoten werden ausgegeben und verlinkt.
       ============================================================ -->

  <xsl:template match="/">
    <result>
      <!-- Generierter Wrapper – KEIN data-src-idx, kein Quell-Äquivalent -->
      <xsl:apply-templates select="*"/>
    </result>
  </xsl:template>

  <!-- Beispiel: Wurzelelement mit Link -->
  <xsl:template match="/*">
    <xsl:element name="{local-name()}">
      <xsl:attribute name="data-src-idx">
        <xsl:value-of select="count(preceding::*) + count(ancestor::*)"/>
      </xsl:attribute>
      <xsl:apply-templates/>
    </xsl:element>
  </xsl:template>

  <!-- Beispiel: Alle Kind-Elemente mit Link -->
  <xsl:template match="*">
    <xsl:element name="{local-name()}">
      <!-- data-src-idx: Brücke zum Quellknoten im linken XML-Pane -->
      <xsl:attribute name="data-src-idx">
        <xsl:value-of select="count(preceding::*) + count(ancestor::*)"/>
      </xsl:attribute>
      <!-- Eigene Attribute des Quellknotens übernehmen -->
      <xsl:apply-templates select="@*"/>
      <!-- Texte und Kind-Elemente verarbeiten -->
      <xsl:apply-templates select="node()"/>
    </xsl:element>
  </xsl:template>

  <!-- Attribute 1:1 kopieren -->
  <xsl:template match="@*">
    <xsl:copy/>
  </xsl:template>


  <!-- ============================================================
       MUSTER 3: xsl:for-each mit Link
       Wenn Elemente per for-each iteriert werden, muss data-src-idx
       ebenfalls im Kontext des Quellknotens gesetzt werden.
       ============================================================ -->

  <!--
  <xsl:template match="/bestellungen">
    <liste>
      <xsl:for-each select="bestellung">
        <eintrag>
          <xsl:attribute name="data-src-idx">
            <xsl:value-of select="count(preceding::*) + count(ancestor::*)"/>
          </xsl:attribute>
          <xsl:value-of select="kunde"/>
        </eintrag>
      </xsl:for-each>
    </liste>
  </xsl:template>
  -->

</xsl:stylesheet>
