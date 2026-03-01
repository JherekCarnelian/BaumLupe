#!/bin/bash
# XML-Viewer starten – nutzt das venv im Home-Verzeichnis
set -e
cd "$(dirname "$0")"
exec ~/xmlviewer-venv/bin/python3 main.py "$@"
