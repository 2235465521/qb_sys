import re
import json
import os
import urllib.parse
from django.db import connections
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings
from django.http import FileResponse, Http404
from companies.models import Company
from django.core.cache import cache

class CompanyFederatedStandardsAPIView(APIView):
    """
    企业国标/行标等主元数据实时联邦查询接口
    """
    permission_classes = [AllowAny]

    def clean_draft_units(self, raw_text):
        """
        清洗起草单位或起草人文本的容错逻辑
        """
        if not raw_text:
            return []
            
        text = str(raw_text).strip()
        text = re.sub(r'[,，、;；﹑]', '|', text)
        text = re.sub(r'等(\s|$)', '', text)
        text = text.replace('等|', '|')
        
        items = [u.strip() for u in text.split('|') if u.strip()]
        
        cleaned_items = []
        for item in items:
            if item.endswith('等') and len(item) > 1:
                item = item[:-1]
            if item and item != '等':
                cleaned_items.append(item)
                
        return cleaned_items

    def get(self, request, pk):
        try:
            company = Company.objects.get(pk=pk)
        except Company.DoesNotExist:
            return Response({'error': '未找到该企业'}, status=404)
        
        scope = request.query_params.get('scope', 'expanded')
        if scope not in ['core', 'expanded']:
            scope = 'expanded'

        from companies.services import FederatedStandardService
        response_data = FederatedStandardService.get_company_standards_summary(company, scope=scope)
        return Response(response_data)

    def _map_status(self, status_code, implement_date=None):
        # 0: 废止, 1: 现行, 2: 即将实施
        mapping = {
            0: '废止',
            1: '现行',
            2: '即将实施'
        }
        status_str = mapping.get(status_code, '现行')

        # 如果是“即将实施”，但实施日期已到，动态将其更新为“现行”
        if status_str == '即将实施' and implement_date:
            import datetime
            if isinstance(implement_date, (datetime.date, datetime.datetime)):
                current_date = datetime.date.today()
                if current_date >= implement_date:
                    status_str = '现行'
            elif isinstance(implement_date, str):
                try:
                    # 尝试解析 ISO 格式日期字符串 (如 YYYY-MM-DD 或 YYYY-MM-DDT...)
                    date_str = implement_date.split('T')[0]
                    imp_date = datetime.date.fromisoformat(date_str)
                    current_date = datetime.date.today()
                    if current_date >= imp_date:
                        status_str = '现行'
                except:
                    pass
        return status_str

class FederatedStandardDownloadAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        file_path = request.query_params.get('file_path')
        if not file_path:
            return Response({"error": "缺少 file_path 参数"}, status=400)
            
        base_dir = os.path.dirname(settings.SHARED_DISK_ROOT.rstrip('/\\'))
        full_path = os.path.join(base_dir, file_path.replace('/', os.sep).replace('\\', os.sep))
        
        if not os.path.exists(full_path):
            raise Http404(f"文件不存在: {full_path}")
            
        filename = os.path.basename(full_path)
        response = FileResponse(open(full_path, 'rb'), content_type='application/pdf')
        encoded_filename = urllib.parse.quote(filename)
        response['Content-Disposition'] = f"attachment; filename*=UTF-8''{encoded_filename}"
        return response
