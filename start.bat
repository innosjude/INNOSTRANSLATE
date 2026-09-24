@echo off
echo INNOSTRANSLATE local launcher
echo.
echo IMPORTANT: FFmpeg must be installed and available on PATH.
echo Also set HF_TOKEN before starting:
echo   set HF_TOKEN=hf_your_token_here
echo.
python -m pip install -r requirements.txt
python app.py
pause
