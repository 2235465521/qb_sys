import re
from django.db import connections
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from companies.models import Company

class CompanyFederatedStandardsAPIView(APIView):
    """
    企业国标/行标等主元数据实时联邦查询接口
    """
    permission_classes = [AllowAny]  # 视项目实际权限修改，目前方便测试先开放

    def clean_draft_units(self, raw_text):
        """
        清洗起草单位或起草人文本的容错逻辑：
        1. 统一处理多种分隔符（， , 、 ; ； ﹑）
        2. 剔除脏数据中的“等”字
        3. 返回清晰的数组
        """
        if not raw_text:
            return []
            
        text = str(raw_text).strip()
        # 将所有可能的不规范分隔符统一替换为 '|'
        text = re.sub(r'[,，、;；﹑]', '|', text)
        
        # 剔除末尾或独立的"等"字，例如：A公司等 -> A公司
        # 兼容性替换：如果有 "A等|B" -> "A|B"
        text = re.sub(r'等(\s|$)', '', text)
        text = text.replace('等|', '|')
        
        # 分割并过滤空白项
        items = [u.strip() for u in text.split('|') if u.strip()]
        
        # 兜底清理：如果在中间还是黏连了“等”，在项级别截取
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
        
        # 优先使用管理员填写的强制绑定 ID（如果未来加了这个字段），目前按公司全名搜索
        # 去除两端空格，处理可能的容错
        search_name = company.name.strip()
        
        # 执行跨库高性能原生 SQL 查询
        try:
            with connections['stsc_db'].cursor() as cursor:
                # 强制使用 utf8mb4 编码，解决 pymysql 默认 latin-1 报错问题
                cursor.execute("SET NAMES utf8mb4;")
                
                # 联表获取该企业参与起草的标准信息
                # 使用 LIKE 解决 "公司名等"、"公司A、公司B" 黏连的脏数据匹配问题
                query = """
                    SELECT 
                        v.std_id, 
                        v.std_chinesename, 
                        v.std_type, 
                        v.release_date, 
                        v.implement_date,
                        v.ex_state as status, 
                        v.drafter, 
                        r.role_type, 
                        r.rank_order
                    FROM unit_dict u
                    JOIN std_unit_relation r ON u.unit_id = r.unit_id
                    JOIN view_std_full v ON r.base_id = v.id
                    WHERE u.unit_name LIKE %s
                    ORDER BY v.release_date DESC
                    LIMIT 500
                """
                cursor.execute(query, [f"%{search_name}%"])
                columns = [col[0] for col in cursor.description]
                results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            return Response({
                'error': '连接 STSC 联邦数据库失败或查询异常',
                'details': str(e)
            }, status=500)
            
        standards = []
        for row in results:
            # 清洗起草人/起草单位字符串
            clean_drafters = self.clean_draft_units(row.get('drafter', ''))
            
            standards.append({
                'standard_no': row['std_id'],
                'title': row['std_chinesename'],
                'type': row['std_type'],
                'release_date': row['release_date'].isoformat() if row['release_date'] else None,
                'implement_date': row['implement_date'].isoformat() if row['implement_date'] else None,
                'status': row['status'],
                'drafters': clean_drafters,  # 返回清洗后的数组
                'raw_drafter': row.get('drafter', ''), # 备用：保留原始脏数据供前端排查
                'participation': {
                    'role_type': row['role_type'],
                    'rank_order': row['rank_order'],
                }
            })
            
        return Response({
            'company_id': company.id,
            'company_name': search_name,
            'total_standards': len(standards),
            'standards': standards
        })
