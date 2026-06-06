@echo off
cd /d "%~dp0"
echo === Video Intelligence: one-time setup ===
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Done installing Python packages.
echo.
echo For transcription you also need FFmpeg (one time):
echo     winget install Gyan.FFmpeg     ^(then open a NEW window^)
echo.
echo Next steps:
echo   1^) Copy .env.example to .env and add your ANTHROPIC_API_KEY ^(optional^)
echo   2^) Double-click run_app.bat
echo.
pause
