@echo off
REM Windows-Build mit PyInstaller
cd /d "%~dp0"

python -m PyInstaller build.spec --onedir --windowed --clean

echo.
echo Build fertig: dist\xmlViewer\xmlViewer.exe
