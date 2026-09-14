"""
doubao_mcp_server.py — 豆包电脑端 MCP (Model Context Protocol) 连接器服务端

专为豆包桌面客户端「新建自定义连接器」设计：
- 传输类型：HTTP
- 服务器 URL：http://127.0.0.1:8088/mcp
- 协议标准：Model Context Protocol (MCP 2.x Streamable HTTP)
- 架构：统一跨库联邦检索（支持本地企标库 emis_db 与外部权威标准库 stsc_standard_database）
"""

import os
import sys
import json
from pathlib import Path

# 1. 初始化并加载 Django 环境
BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from django.conf import settings
from mcp.server.mcpserver import MCPServer
from standards.utils.doubao_query import query_company_standards

# 2. 创建 MCP 服务实例
mcp_server = MCPServer("企标与企业资产连接器")

@mcp_server.tool(
    name="search_company_standards",
    description="查询某家企业、公司、科研院所或事业单位名下的标准专属数据库（涵盖国家标准、行业标准、地方标准、团体标准及企业标准）。当用户询问任何企业或机构的标准、企标、团标、国标、标准清单或需要标准原文下载时，必须调用此工具。"
)
def search_company_standards(
    company_name: str,
    standard_type: str = "all",
    status: str = "all",
    limit: int = 20
) -> str:
    print(f"[EMIS MCP] Called search_company_standards: company_name='{company_name}', standard_type='{standard_type}', status='{status}', limit={limit}", flush=True)
    base_url = getattr(settings, 'PUBLIC_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
    api_key = getattr(settings, 'DOUBAO_API_KEY', '')

    result = query_company_standards(
        company_name=company_name,
        standard_type=standard_type,
        status_filter=status,
        limit=limit,
        base_url=base_url,
        api_key=api_key
    )
    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    print("[EMIS] Starting Doubao MCP Server...")
    print("   - MCP URL: http://127.0.0.1:8088/mcp")
    print("   - Transport: HTTP (Streamable HTTP)")
    mcp_server.run(transport="streamable-http", host="0.0.0.0", port=8088, streamable_http_path="/mcp")
