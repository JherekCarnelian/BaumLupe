#!/usr/bin/env python3
"""Einstiegspunkt für den XML-Viewer.

Aufruf:
    ./run.sh [datei.xml [xsl1.xsl [xsl2.xsl ...]] [--new-column xsl3.xsl ...]] [--x X] [--y Y]

Jedes XSL-Argument öffnet eine weitere Pane in Spalte 0 (untereinander).
--new-column leitet eine neue Spalte ein; alle danach folgenden XSL-Dateien
bis zum nächsten --new-column landen vertikal gestapelt in dieser neuen Spalte.

Beispiel:
    viewer.py datei.xml a.xsl b.xsl --new-column c.xsl d.xsl --new-column e.xsl
    → Spalte 0: a + b  │  Spalte 1: c + d  │  Spalte 2: e

Optionen:
    --x X   Fenster-Position horizontal (Pixel vom linken Bildschirmrand)
    --y Y   Fenster-Position vertikal   (Pixel vom oberen Bildschirmrand)

Mehrere Instanzen gleichzeitig sind problemlos möglich.
"""

import os
import sys
import argparse

from PySide6.QtWidgets import QApplication

from version import __version__
from ui.main_window import MainWindow


def main() -> None:
    parser = argparse.ArgumentParser(description="XML Viewer")
    parser.add_argument("xml", nargs="?", help="XML-Datei")
    parser.add_argument("xsl", nargs="*",
                        help="XSL-Stylesheet(s) – jedes öffnet eine Pane in Spalte 0")
    parser.add_argument("--new-column", nargs="+", action="append", dest="new_columns",
                        metavar="XSL",
                        help="Neue Spalte; folgende XSL-Dateien landen darin (wiederholbar)")
    parser.add_argument("--x", type=int, dest="win_x", metavar="X",
                        help="Fenster-X-Position (Pixel)")
    parser.add_argument("--y", type=int, dest="win_y", metavar="Y",
                        help="Fenster-Y-Position (Pixel)")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("XML Viewer")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("xmlviewer")

    window = MainWindow()
    window.show()

    # Position nach show() setzen – so wird sie von allen Window-Managern respektiert
    if args.win_x is not None and args.win_y is not None:
        window.move(args.win_x, args.win_y)

    if args.xml:
        if os.path.isfile(args.xml):
            window._load_xml(args.xml)

    # Spalte 0: alle XSL-Argumente vor dem ersten --new-column
    for i, xsl in enumerate(args.xsl):
        if os.path.isfile(xsl):
            if i == 0:
                window._load_xsl(xsl)
            else:
                window._add_transform_pane(xsl_path=xsl, direction='vertical')

    # Jede --new-column-Gruppe öffnet eine neue Spalte
    for col_xsls in (args.new_columns or []):
        for i, xsl in enumerate(col_xsls):
            if os.path.isfile(xsl):
                if i == 0:
                    # Erste Pane der Gruppe → neue Spalte anlegen
                    window._add_transform_pane(xsl_path=xsl, direction='horizontal')
                else:
                    # Weitere Panes → vertikal in derselben (letzten) Spalte
                    window._add_transform_pane(xsl_path=xsl, direction='vertical')

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
