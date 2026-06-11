@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   AI 高考志愿顾问 — Web 版启动
echo ========================================
echo.
echo 正在启动 Streamlit 服务...
echo 启动后浏览器会自动打开 http://localhost:8501
echo.
echo 按 Ctrl+C 停止服务
echo.
streamlit run app.py
pause
