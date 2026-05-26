"""
standards.views.analysis_views — 引用解析视图（模块二）
"""

from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser

from standards import services


class NormativeReferenceUploadView(APIView):
    """
    POST /api/client/analysis/upload/
    上传规范性引用 Excel 文件，触发解析流程
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser]

    def post(self, request):
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': '请上传 Excel 文件'}, status=status.HTTP_400_BAD_REQUEST)

        if not file_obj.name.endswith(('.xlsx', '.xls')):
            return Response({'error': '仅支持 .xlsx 或 .xls 格式'}, status=status.HTTP_400_BAD_REQUEST)

        result = services.parse_normative_reference_excel(file_obj)
        return Response(result, status=status.HTTP_200_OK)


class CitationRankingView(APIView):
    """
    GET /api/client/analysis/citation-rank/
    国标引用热度排行榜
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get('limit', 20))
        ranking = list(services.get_citation_ranking(limit=limit))
        return Response({'results': ranking, 'count': len(ranking)})


import openpyxl
import io
from django.http import HttpResponse

class ExportCitationRankingView(APIView):
    """
    GET /api/client/analysis/export-excel/
    导出引用排行榜 Excel，支持自定义限额
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 10))
        except ValueError:
            limit = 10
            
        ranking = services.get_citation_ranking(limit=limit)
        
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "国标引用热度排行榜"
        
        # Write headers
        ws.append(["排名", "标准号", "最新标准号", "被引用次数"])
        
        # Write data rows
        for idx, item in enumerate(ranking):
            ws.append([
                idx + 1,
                item.get('standard_no', ''),
                item.get('title', ''),
                item.get('citation_count', 0)
            ])
            
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        
        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=citation_ranking_top{limit}.xlsx'
        return response
