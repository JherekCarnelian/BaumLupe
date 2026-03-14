@echo off
REM Windows-Build mit PyInstaller
cd /d "%~dp0"

REM Alte Build-Artefakte vollständig entfernen
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

python -m PyInstaller build.spec --onedir --windowed --clean

echo.
echo Build fertig: dist\xmlViewer\xmlViewer.exe
