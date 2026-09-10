@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动网页版（把终端里显示的 http://192.168.x.x:8080 发给同学）
python serve.py
pause
