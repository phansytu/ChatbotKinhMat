@echo off
title KinhMat AI Chatbot
color 0B

echo ============================================
echo   KINH MAT AI CHATBOT - Khoi dong...
echo ============================================
echo.

:: Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Chua cai Python! Tai tai: https://python.org
    pause
    exit
)

:: Cai thu vien neu chua co
echo [1] Kiem tra va cai thu vien...
pip install -r requirements.txt -q

echo.
echo [2] Kiem tra file knowledge.txt...
if not exist "data\knowledge.txt" (
    echo [CANH BAO] Khong tim thay data\knowledge.txt
    echo           Chatbot se chay o che do han che
) else (
    echo [OK] Tim thay data\knowledge.txt
)

echo.
echo [3] Khoi dong server Flask...
echo.
echo  Server: http://localhost:5000
echo  Chat:   http://localhost:5000
echo  API:    http://localhost:5000/api/chat
echo  Health: http://localhost:5000/api/health
echo.
echo  Nhan Ctrl+C de dung server
echo ============================================
echo.

python app.py

pause
