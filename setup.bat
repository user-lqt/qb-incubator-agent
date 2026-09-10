@echo off
chcp 65001 >nul
echo ============================================
echo  安装依赖（需要已装 Python 3.10+）
echo ============================================
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo [失败] 请先安装 Python：https://www.python.org/downloads/
  echo        安装时记得勾选 "Add Python to PATH"
) else (
  echo.
  echo [完成] 依赖装好了。接下来：
  echo   1. 复制 .env.example 为 .env，填入自己的 DEEPSEEK_API_KEY
  echo   2. 双击 run.bat 开始对话
)
pause
