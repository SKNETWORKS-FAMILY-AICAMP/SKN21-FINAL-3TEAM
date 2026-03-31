@echo off
echo Starting installation...
.venv\Scripts\python.exe -m pip install kiwipiepy==0.22.2
echo Installation finished with exit code %errorlevel%
