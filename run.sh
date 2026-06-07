#!/bin/bash
# BaumLupe starten – nutzt das venv im Home-Verzeichnis
set -e
cd "$(dirname "$0")"
exec ~/baumlupe-venv/bin/python3 main.py "$@"
