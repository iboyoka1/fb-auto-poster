:: FB AUTO-POSTER - RENDER DEPLOYMENT QUICK START
:: ==============================================

@echo off
setlocal enabledelayedexpansion

echo.
echo ========================================================
echo     FB AUTO-POSTER - GITHUB & RENDER DEPLOYMENT
echo ========================================================
echo.
echo BEFORE YOU START:
echo   1. Create GitHub account: https://github.com/signup
echo   2. Create new repo: https://github.com/new
echo      - Name: fb-auto-poster
echo      - Public or Private (your choice)
echo.
echo THEN RUN THESE COMMANDS (replace YOUR_USERNAME):
echo.
echo ========================================================
echo.

echo cd c:\Users\AWST\Desktop\fb-group-auto-post-main
cd c:\Users\AWST\Desktop\fb-group-auto-post-main

echo.
echo git remote add origin https://github.com/YOUR_USERNAME/fb-auto-poster.git
echo git branch -M main
echo git push -u origin main
echo.
echo ========================================================
echo.
echo THEN:
echo   1. Go to https://render.com
echo   2. Sign in with GitHub
echo   3. Click "New +" ^> "Web Service"
echo   4. Select fb-auto-poster repository
echo   5. Keep default settings
echo   6. Click "Create Web Service"
echo   7. Wait 3-5 minutes...
echo   8. Your app is LIVE!
echo.
echo Access: https://fb-auto-poster.onrender.com
echo Username: admin
echo Password: password123
echo.
echo ========================================================

pause
