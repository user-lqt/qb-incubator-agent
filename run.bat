@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 启动孵化者（输入 exit 退出，Ctrl+C 也可退出）
python agent.py
pause
