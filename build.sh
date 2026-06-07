#!/bin/bash
# Linux-Build mit PyInstaller
set -e
cd "$(dirname "$0")"

python3 -m PyInstaller build.spec --onedir --clean

echo ""
echo "Build fertig: dist/BaumLupe/BaumLupe"
