@echo off
REM FB AUTO-POSTER - Windows EXE Builder
REM This script creates a standalone Windows executable

echo.
echo =====================================================
echo  FB AUTO-POSTER - Windows EXE Builder
echo =====================================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller -q
)

REM Install latest requirements
echo Installing dependencies...
pip install -q -r requirements.txt

REM Create dist directory
if not exist "dist" mkdir dist

REM Build executable
echo.
echo Building executable...
echo This may take a few minutes...
echo.

pyinstaller ^
    --onefile ^
    --console ^
    --name "FB-Auto-Poster" ^
    --add-data "static:static" ^
    --add-data "templates:templates" ^
    --hidden-import=flask ^
    --hidden-import=werkzeug ^
    --hidden-import=jinja2 ^
    --hidden-import=bcrypt ^
    --hidden-import=jwt ^
    --hidden-import=cryptography ^
    --hidden-import=security ^
    --hidden-import=setup_wizard ^
    --distpath "dist\windows" ^
    --buildpath "build" ^
    --specpath "specs" ^
    run_server.py

REM Check if build was successful
if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

REM Create shortcuts
echo.
echo Creating desktop shortcut...

REM This will be replaced with a proper shortcut creation script
REM For now, just copy the exe to dist

echo.
echo =====================================================
echo  BUILD COMPLETE!
echo =====================================================
echo.
echo Executable location:
echo   dist\windows\FB-Auto-Poster.exe
echo.
echo Next steps:
echo   1. Test the executable on a clean Windows PC
echo   2. Create an NSIS installer (optional)
echo   3. Sign the executable (recommended)
echo.
pause
