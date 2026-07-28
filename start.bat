@echo off
set PYTHONPATH=%~dp0backend
echo Starting PDD Rating Dashboard on http://127.0.0.1:8771
C:\Users\s\AppData\Local\Programs\Python\Python314\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8771
pause
