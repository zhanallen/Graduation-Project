@echo off
echo ==========================================
echo 📦 Starting build process for DE Applications
echo ==========================================

set PYINSTALLER=.venv\Scripts\pyinstaller.exe

if not exist "%PYINSTALLER%" (
    echo ❌ PyInstaller not found in .venv! Installing it...
    .venv\Scripts\pip.exe install pyinstaller
)

echo.
echo 🚀 Building MultiAudioDownloader...
"%PYINSTALLER%" --noconfirm MultiAudioDownloader.spec
if %errorlevel% neq 0 (
    echo ❌ Failed to build MultiAudioDownloader!
    exit /b 1
)

echo.
echo 🚀 Building StegoPacker...
"%PYINSTALLER%" --noconfirm StegoPacker.spec
if %errorlevel% neq 0 (
    echo ❌ Failed to build StegoPacker!
    exit /b 1
)

echo.
echo 🚀 Building StegoPlayer...
"%PYINSTALLER%" --noconfirm StegoPlayer.spec
if %errorlevel% neq 0 (
    echo ❌ Failed to build StegoPlayer!
    exit /b 1
)

echo.
echo ==========================================
echo 🎉 All builds completed successfully!
echo ==========================================
