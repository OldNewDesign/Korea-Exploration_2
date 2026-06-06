@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"
echo Starting Video Intelligence...
echo If your browser does not open automatically, go to http://localhost:8501
python -m streamlit run app.py
pause
