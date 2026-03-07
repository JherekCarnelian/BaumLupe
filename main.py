#!/usr/bin/env python3
"""Einstiegspunkt für den XML-Viewer.

Aufruf:
    ./run.sh [datei.xml [stylesheet.xsl]] [--x X] [--y Y]

Optionen:
    --x X   Fenster-Position horizontal (Pixel vom linken Bildschirmrand)
    --y Y   Fenster-Position vertikal   (Pixel vom oberen Bildschirmrand)

Mehrere Instanzen gleichzeitig sind problemlos möglich.
"""

import sys
import argparse

from PySide6.QtWidgets import QApplication

from version import __version__
from ui.main_window import MainWindow


def main() -> None:
    parser = argparse.ArgumentParser(description="XML Viewer")
    parser.add_argument("xml", nargs="?", help="XML-Datei")
    parser.add_argument("xsl", nargs="?", help="XSL-Stylesheet")
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
        import os
        if os.path.isfile(args.xml):
            window._load_xml(args.xml)

    if args.xsl:
        import os
        if os.path.isfile(args.xsl):
            window._load_xsl(args.xsl)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
