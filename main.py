#!/usr/bin/env python3
"""Einstiegspunkt für den XML-Viewer.

Aufruf:
    ./run.sh [datei.xml [stylesheet.xsl]]

Mehrere Instanzen gleichzeitig sind problemlos möglich.
"""

import sys
import os

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("XML Viewer")
    app.setOrganizationName("xmlviewer")

    window = MainWindow()
    window.show()

    args = sys.argv[1:]

    if args and os.path.isfile(args[0]):
        window._load_xml(args[0])

    if len(args) >= 2 and os.path.isfile(args[1]):
        window._load_xsl(args[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
