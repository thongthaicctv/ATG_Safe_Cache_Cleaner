@echo off
chcp 65001
title Build ATG Safe Cache Cleaner

echo ================================
echo BUILD ATG SAFE CACHE CLEANER
echo ================================

cd /d "%~dp0"

pip install -r requirements.txt

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

pyinstaller build_onefile.spec --clean

echo.
echo DONE.
echo EXE:
echo dist\ATG_Safe_Cache_Cleaner.exe

pause