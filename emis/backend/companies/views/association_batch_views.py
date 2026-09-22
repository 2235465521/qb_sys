"""
companies.views.association_batch_views — 社团名单批量查标与合并导出视图
"""

from urllib.parse import quote
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.parsers import MultiPartParser, JSONParser, FormParser

from companies.services_association import AssociationBatchService


class AssociationBatchQueryView(APIView):
    """
    POST /api/client/search/associations/batch-query/
    批量查询社团/协会标准资产统计

    支持两种传入方式：
      1. Multipart Form: 上传 Excel 文件（键名 'file'）
      2. JSON Body: { "names": ["福建省联合采购协会", "泉州市会展业联合会"] }
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, *args, **kwargs):
        names = []

        # 方式 1：上传了 Excel 文件
        if 'file' in request.FILES:
            upload_file = request.FILES['file']
            try:
                content = upload_file.read()
                names = AssociationBatchService.parse_excel_association_names(content)
            except Exception as e:
                return Response(
                    {'error': f'Excel 文件解析失败: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        # 方式 2：JSON 传入 names 数组
        elif 'names' in request.data:
            raw_names = request.data.get('names', [])
            if isinstance(raw_names, list):
                names = [str(n).strip() for n in raw_names if str(n).strip()]
            elif isinstance(raw_names, str):
                names = [line.strip() for line in raw_names.splitlines() if line.strip()]

        if not names:
            return Response(
                {'error': '未能从上传文件中识别到有效的社团/协会名称，请确保包含“社团名称/协会名称/单位名称”列，或提供非空名称列表'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            result = AssociationBatchService.batch_query_associations(names)
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {'error': f'批量查询标准资产失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AssociationBatchExportView(APIView):
    """
    POST /api/client/search/associations/batch-export/
    批量合并导出社团标准概览及明细全集为单张 Excel 表格
    
    载荷：
      {
        "names": ["福建省联合采购协会", ...]
      }
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request, *args, **kwargs):
        names = request.data.get('names', [])
        if not names or not isinstance(names, list):
            return Response(
                {'error': '请提供需要导出的社团/协会名称列表 (names 数组)'},
                status=status.HTTP_400_BAD_REQUEST
            )

        clean_names = [str(n).strip() for n in names if str(n).strip()]
        if not clean_names:
            return Response(
                {'error': '社团名称列表为空'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            excel_bytes, filename = AssociationBatchService.export_associations_merged_excel(clean_names)
        except Exception as e:
            return Response(
                {'error': f'生成合并 Excel 报表失败: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        quoted_filename = quote(filename)
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quoted_filename}"
        return response
