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
        
        search_name = company.name.strip()
        
        try:
            with connections['stsc_db'].cursor() as cursor:
                cursor.execute("SET NAMES utf8mb4;")
                query = """
                    SELECT 
                        v.std_id, 
                        v.std_chinesename, 
                        v.std_type, 
                        v.release_date, 
                        v.implement_date, 
                        v.ex_state as status, 
                        h.draft_unit as drafter,
                        f.file_path,
                        r.rank_order
                    FROM mydate.unit_dict u
                    JOIN mydate.std_unit_relation r ON u.unit_id = r.unit_id
                    JOIN mydate.view_std_full v ON r.base_id = v.id
                    LEFT JOIN mydate.std_extend_h h ON v.id = h.base_id
                    LEFT JOIN mydate.std_filepath f ON v.id = f.base_id
                    WHERE u.unit_name = %s
                    ORDER BY v.release_date DESC
                """
                cursor.execute(query, [search_name])
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            return Response({
                'error': '连接 STSC 联邦数据库失败或查询异常',
                'details': str(e)
            }, status=500)
            
        formatted_results = []
        for row in results:
            drafters_raw = row.get('drafter', '')
            drafters_list = self.clean_draft_units(drafters_raw)
            
            formatted_results.append({
                'standard_no': row.get('std_id', ''),
                'title': row.get('std_chinesename', ''),
                'type': row.get('std_type', ''),
                'release_date': row.get('release_date').isoformat() if row.get('release_date') else None,
                'implement_date': row.get('implement_date').isoformat() if row.get('implement_date') else None,
                'status': self._map_status(row.get('status')),
                'drafters': drafters_list,
                'file_path': row.get('file_path'),
                'rank_order': row.get('rank_order')
            })
            
        unique_results = []
        seen_stds = set()
        for item in formatted_results:
            if item['standard_no'] not in seen_stds:
                seen_stds.add(item['standard_no'])
                unique_results.append(item)
                
        return Response({
            'company_id': company.id,
            'company_name': search_name,
            'total_standards': len(unique_results),
            'standards': unique_results
        })

    def _map_status(self, status_code):
        mapping = {
            1: '现行',
            2: '废止',
            3: '即将实施'
        }
        return mapping.get(status_code, '现行')

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
