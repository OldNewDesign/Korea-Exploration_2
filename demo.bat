@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
echo Building demo library (no keys/network needed)...
python process_videos.py --demo
echo.
echo Opening the guide and map...
start "" "output\video_guide.html"
start "" "output\video_map.html"
pause
