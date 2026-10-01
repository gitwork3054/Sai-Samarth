@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto ready
where py >nul 2>nul
if errorlevel 1 (
  python -m venv .venv
) else (
  py -3 -m venv .venv
)
if errorlevel 1 goto failed
:ready
if not exist .env copy /Y .env.example .env >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 goto failed
".venv\Scripts\python.exe" manage.py shell -c "from travel.models import Package; from django.core.management import call_command; call_command('generate_demo') if not Package.objects.exists() else None"
if errorlevel 1 goto failed
echo.
echo Open http://127.0.0.1:8000/ in your browser.
echo Keep this window open while using the website.
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
exit /b
:failed
echo.
echo Setup failed. Check the error shown above. Install Python 3.12 or 3.13 if Python is missing.
pause
exit /b 1
