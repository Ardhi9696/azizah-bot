@echo off
echo Menjalankan bot...

REM Pindah ke folder lokasi batch file (biar run.py pasti ketemu)
cd /d "%~dp0"

REM Jalankan python dengan path absolut
"C:\Users\user-x\AppData\Local\Programs\Python\Python311\python.exe" run.py

pause
