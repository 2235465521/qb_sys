"""
standards.views.open_views — 豆包大模型连接器专属开放接口

包含：
  DoubaoCompanyStandardsView  — 一站式查询某企业名下的企业标准与团体标准
  DoubaoStandardDownloadView  — 专属标准 PDF 文件下载通道
  DoubaoSchemaView            — 动态生成并输出符合 OpenAPI 3.0 的 Schema 规范
"""

import os
from urllib.parse import quote
from django.conf import settings
from django.http import Http404, FileResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from companies.models import Company
from standards.models import Standard
from standards.utils.doubao_query import query_company_standards


def verify_doubao_api_key(request) -> bool:
    """校验豆包连接器 API Key（支持 Bearer Token 或 Query 传参）"""
    configured_key = getattr(settings, 'DOUBAO_API_KEY', '')
    if not configured_key:
        return True  # 未配置密钥时默认放行（便于本地调试）

    # 1. 优先校验 Header 中的 Authorization: Bearer <key>
    auth_header = request.headers.get('Authorization') or request.META.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:].strip()
        if token == configured_key:
            return True

    # 2. 兼容 Query 参数 ?key= 或 ?api_key=
    query_key = request.query_params.get('key') or request.query_params.get('api_key')
    if query_key == configured_key:
        return True

    return False


class DoubaoCompanyStandardsView(APIView):
    """
    GET /api/open/doubao/company-standards/
    豆包连接器一站式查询接口：根据企业名称关键词，直接返回企业信息、标准清单及下载链接。
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # 1. 安全鉴权
        if not verify_doubao_api_key(request):
            return Response(
                {
                    "success": False,
                    "error": "Unauthorized",
                    "message": "API Key 无效或未提供。请在请求头设置 Authorization: Bearer <token>"
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # 2. 获取并校验参数
        company_name = request.query_params.get('company_name', '').strip()
        if not company_name:
            return Response(
                {
                    "success": False,
                    "error": "Bad Request",
                    "message": "缺少必填参数 'company_name'（企业名称或关键词）"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        standard_type = request.query_params.get('standard_type', 'all').strip().lower()
        std_status = request.query_params.get('status', 'all').strip().lower()

        try:
            limit = int(request.query_params.get('limit', 20))
            limit = max(1, min(limit, 50))  # 限制在 1 ~ 50 条之间，防止大模型 Token 溢出
        except (ValueError, TypeError):
            limit = 20

        # 3. 执行跨库统一联邦检索
        base_url = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
        if not base_url:
            base_url = request.build_absolute_uri('/')[:-1]
        api_key_param = getattr(settings, 'DOUBAO_API_KEY', '')

        result = query_company_standards(
            company_name=company_name,
            standard_type=standard_type,
            status_filter=std_status,
            limit=limit,
            base_url=base_url,
            api_key=api_key_param
        )
        result["filter"] = {
            "standard_type": standard_type,
            "status": std_status,
            "limit": limit
        }
        return Response(result)



class DoubaoStandardDownloadView(APIView):
    """
    GET /api/open/doubao/download/<int:pk>/
    豆包连接器专用标准 PDF 下载通道（验证 API Key 即可安全直链下载）
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request, pk):
        if not verify_doubao_api_key(request):
            return Response(
                {"error": "Unauthorized: 无效的文件下载密钥凭证"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            standard = Standard.objects.get(pk=pk)
        except Standard.DoesNotExist:
            raise Http404("标准不存在")

        shared_root = getattr(settings, 'SHARED_DISK_ROOT', r"Y:\磁盘阵列\标准文件下载\企标下载")
        file_path = None

        # 1. 优先策略：先尝试 disk_filename
        if standard.disk_filename:
            norm_disk_filename = standard.disk_filename.replace('\\', '/')
            disk_file_path = os.path.join(shared_root, norm_disk_filename)
            if os.path.exists(disk_file_path):
                file_path = disk_file_path

        # 2. 降级策略：尝试 pdf_file
        if not file_path and standard.pdf_file:
            rel_path = standard.pdf_file.name.replace('\\', '/')
            disk_file_path = os.path.join(shared_root, rel_path)
            if os.path.exists(disk_file_path):
                file_path = disk_file_path
            else:
                media_file_path = os.path.join(settings.MEDIA_ROOT, rel_path)
                if os.path.exists(media_file_path):
                    file_path = media_file_path
                elif rel_path.startswith('media/'):
                    clean_path = rel_path.replace('media/', '', 1)
                    clean_file_path = os.path.join(settings.MEDIA_ROOT, clean_path)
                    if os.path.exists(clean_file_path):
                        file_path = clean_file_path

        if not file_path:
            raise Http404("此标准尚未关联有效的 PDF 物理文件")

        filename = os.path.basename(file_path)
        try:
            content_disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
        except Exception:
            content_disposition = f"attachment; filename={quote(filename)}"

        response = FileResponse(open(file_path, 'rb'), content_type='application/pdf')
        response['Content-Type'] = 'application/pdf'
        response['Content-Disposition'] = content_disposition
        return response


class DoubaoSchemaView(APIView):
    """
    GET /api/open/doubao/schema/
    动态输出符合 OpenAPI 3.0.0 规范的 JSON 描述，便于在豆包连接器中通过 URL 一键导入
    """
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        base_url = getattr(settings, 'PUBLIC_BASE_URL', '').rstrip('/')
        if not base_url:
            base_url = request.build_absolute_uri('/')[:-1]

        schema = {
            "openapi": "3.0.0",
            "info": {
                "title": "企标管理系统 (EMIS) 豆包连接器",
                "description": "提供企业标准（企标）及团体标准（团标）的数据查询与下载能力。根据公司名称实时检索其名下所有标准资产及 PDF 下载链接。",
                "version": "1.0.0"
            },
            "servers": [
                {
                    "url": base_url,
                    "description": "EMIS 企标管理系统 API 服务"
                }
            ],
            "paths": {
                "/api/open/doubao/company-standards/": {
                    "get": {
                        "summary": "查询某公司名下的标准资产",
                        "description": "根据企业全称或关键词，一站式查询该企业拥有的企业标准（企标）与团体标准（团标）列表，并返回详情及可下载的 PDF 链接。",
                        "operationId": "getCompanyStandards",
                        "parameters": [
                            {
                                "name": "company_name",
                                "in": "query",
                                "description": "企业名称或关键词，例如：'华为'、'比亚迪'、'宁德时代新能源科技股份有限公司'",
                                "required": True,
                                "schema": {
                                    "type": "string"
                                }
                            },
                            {
                                "name": "standard_type",
                                "in": "query",
                                "description": "标准类型筛选：'all'（全部）、'enterprise'（仅企业标准）、'group'（仅团体标准）",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "enum": ["all", "enterprise", "group"],
                                    "default": "all"
                                }
                            },
                            {
                                "name": "status",
                                "in": "query",
                                "description": "标准状态筛选：'all'（全部）、'active'（现行）、'deprecated'（废止）",
                                "required": False,
                                "schema": {
                                    "type": "string",
                                    "enum": ["all", "active", "deprecated"],
                                    "default": "all"
                                }
                            },
                            {
                                "name": "limit",
                                "in": "query",
                                "description": "最多返回的标准条数（默认 20 条，最大 50 条）",
                                "required": False,
                                "schema": {
                                    "type": "integer",
                                    "default": 20,
                                    "minimum": 1,
                                    "maximum": 50
                                }
                            }
                        ],
                        "responses": {
                            "200": {
                                "description": "成功返回企业标准资产",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "success": {"type": "boolean"},
                                                "matched": {"type": "boolean"},
                                                "company": {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {"type": "string", "description": "企业名称"},
                                                        "credit_code": {"type": "string", "description": "统一社会信用代码"},
                                                        "legal_person": {"type": "string", "description": "法定代表人"},
                                                        "region": {"type": "string", "description": "所在省市区"},
                                                        "ownership_categories": {
                                                            "type": "array",
                                                            "items": {"type": "string"},
                                                            "description": "所有制属性标签，如央企、民营企业等"
                                                        },
                                                        "standards_count_in_db": {"type": "integer", "description": "库中标准总量"}
                                                    }
                                                },
                                                "total_standards": {"type": "integer", "description": "符合筛选条件的总标准数"},
                                                "returned_count": {"type": "integer", "description": "本次返回的标准条数"},
                                                "standards": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "standard_no": {"type": "string", "description": "标准号"},
                                                            "title": {"type": "string", "description": "标准名称"},
                                                            "type_display": {"type": "string", "description": "企业标准 或 团体标准"},
                                                            "status_display": {"type": "string", "description": "现行 / 废止"},
                                                            "publish_date": {"type": "string", "description": "发布日期"},
                                                            "has_pdf": {"type": "boolean", "description": "是否有物理 PDF 文件"},
                                                            "download_url": {"type": "string", "description": "PDF 直接下载链接（可供用户点击）"}
                                                        }
                                                    }
                                                },
                                                "candidate_companies": {
                                                    "type": "array",
                                                    "description": "命中的其他同名/关联候选企业（若有）",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "name": {"type": "string"},
                                                            "standards_count": {"type": "integer"}
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },
                            "401": {
                                "description": "未授权，API Key 缺失或错误"
                            }
                        },
                        "security": [
                            {
                                "BearerAuth": []
                            }
                        ]
                    }
                }
            },
            "components": {
                "securitySchemes": {
                    "BearerAuth": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "APIKey",
                        "description": "请输入 EMIS 系统的 DOUBAO_API_KEY"
                    }
                }
            }
        }
        return Response(schema)
