<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:xs="http://www.w3.org/2001/XMLSchema"
  expand-text="yes">

  <xsl:output method="html" indent="yes" encoding="UTF-8"/>

  <!-- Wurzel-Template: erzeugt eine HTML-Seite -->
  <xsl:template match="/">
    <html>
      <head>
        <meta charset="UTF-8"/>
        <title>XML-Transformation</title>
        <style>
          body  {{ font-family: sans-serif; margin: 1em; background: #f5f5f5; }}
          h1    {{ color: #333; border-bottom: 2px solid #666; padding-bottom: .3em; }}
          table {{ border-collapse: collapse; width: 100%; background: white; }}
          th    {{ background: #444; color: white; padding: .4em .8em; text-align: left; }}
          td    {{ padding: .35em .8em; border-bottom: 1px solid #ddd; }}
          tr:nth-child(even) td {{ background: #f0f0f0; }}
          .path {{ font-family: monospace; color: #555; font-size: .85em; }}
        </style>
      </head>
      <body>
        <h1>Transformiertes Dokument</h1>
        <p class="path">Wurzelelement: <code>{name(/*[1])}</code></p>

        <!-- XSLT 3.0: iterate über alle Kindelemente der Wurzel -->
        <table>
          <tr>
            <th>#</th>
            <th>Element</th>
            <th>Inhalt (gekürzt)</th>
            <th>Attribute</th>
          </tr>
          <xsl:for-each select="/*/*">
            <xsl:variable name="pos" select="position()"/>
            <tr>
              <td>{$pos}</td>
              <td><strong>{name()}</strong></td>
              <td>{substring(normalize-space(.), 1, 80)}{if (string-length(normalize-space(.)) > 80) then '…' else ''}</td>
              <td>
                <xsl:for-each select="@*">
                  <span style="margin-right:.5em"><em>{name()}</em>={.}</span>
                </xsl:for-each>
              </td>
            </tr>
          </xsl:for-each>
        </table>

        <!-- XSLT 3.0: Gesamtzahl der Elemente im Dokument -->
        <p style="margin-top:1em;color:#666;font-size:.9em">
          Gesamt {count(//*)} Elemente im Dokument.
        </p>
      </body>
    </html>
  </xsl:template>

</xsl:stylesheet>
