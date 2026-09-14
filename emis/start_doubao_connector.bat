@echo off
chcp 65001 >nul
title 豆包电脑端 MCP 连接器
echo ============================================================
echo   🚀 正在启动 企标管理系统 (EMIS) 豆包 MCP 连接器服务...
echo ============================================================
echo.
echo   - 传输类型: HTTP
echo   - 服务器 URL: http://127.0.0.1:8088/mcp
echo.
echo   请在豆包「新建自定义连接器」弹窗中填入：
echo     服务器名称: 企标与企业资产连接器
echo     传输类型:   HTTP
echo     服务器 URL: http://127.0.0.1:8088/mcp
echo ============================================================
cd /d %~dp0
python doubao_mcp_server.py
pause
