REM # For JotSearchv0.7-standalone.py with PyInstaller Support, PATCHED for STDERR
@echo off
setlocal

:: Install required packages
pip install pyinstaller requests

:: Create bin directory and download ripgrep
mkdir bin
curl -L -o bin\rg.zip https://github.com/BurntSushi/ripgrep/releases/download/14.1.0/ripgrep-14.1.0-x86_64-pc-windows-msvc.zip

:: Extract ripgrep
powershell -Command "Expand-Archive -Path bin\rg.zip -DestinationPath bin"
move bin\rg-14.1.0-x86_64-pc-windows-msvc\rg.exe bin\rg.exe
rmdir /s /q bin\rg-14.1.0-x86_64-pc-windows-msvc
del bin\rg.zip

:: Build executable
pyinstaller --onefile ^
    --name JotSearch ^
    --add-data "bin;bin" ^
    --icon NONE ^
    --windowed ^
    JotSearch.py

:: Copy assets to dist folder
xcopy bin dist\bin /E /I /Y

echo Build complete! Executable is in dist folder.
endlocal