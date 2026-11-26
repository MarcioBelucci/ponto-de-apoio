@echo off
cd /d "%~dp0"
title Ponto de Apoio
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado. Consulte a secao "Primeira instalacao" do README.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" iniciar.py
if errorlevel 1 (
    echo.
    echo Nao foi possivel iniciar o sistema. Veja a mensagem acima.
    pause
    exit /b 1
)
