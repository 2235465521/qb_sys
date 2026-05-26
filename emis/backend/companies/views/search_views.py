"""
companies.views.search_views — 前台搜企视图（模块一）
"""

from django.http import HttpResponse
from django.core.cache import cache
import json
from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination

from companies.models import Company, CompanyLead
from companies.serializers import CompanyListSerializer, CompanyDetailSerializer, CompanyLeadSerializer
from standards.serializers import StandardListSerializer
from companies import services


class CompanySearchPagination(PageNumberPagination):
    page_size = 9
    page_size_query_param = 'page_size'
    max_page_size = 100


class CompanySearchView(generics.ListAPIView):
    """
    GET /api/client/search/companies/
    多维级联检索（包含行政区划级联、LBS周边检索、标准分类检索与关键词）
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CompanyListSerializer
    pagination_class = CompanySearchPagination

    def get_queryset(self):
        params = self.request.query_params
        
        # 解析 LBS
        lat = params.get('lat')
        lng = params.get('lng')
        radius_km = params.get('radius_km')
        
        center_lat = None
        center_lng = None
        radius = None
        
        if lat and lng and radius_km:
            try:
                center_lat = float(lat)
                center_lng = float(lng)
                radius = float(radius_km)
            except ValueError:
                pass

        return services.search_companies(
            keyword=params.get('keyword', ''),
            province_id=params.get('province_id'),
            city_id=params.get('city_id'),
            district_id=params.get('district_id'),
            center_lat=center_lat,
            center_lng=center_lng,
            radius_km=radius,
            ics=params.get('ics', ''),
            ccs=params.get('ccs', ''),
            standard_logic=params.get('standard_logic', 'OR'),
        )

    def list(self, request, *args, **kwargs):
        params = request.query_params
        # 构造唯一的缓存 Key
        cache_parts = []
        for key in sorted(params.keys()):
            cache_parts.append(f"{key}={params.get(key)}")
        cache_key = "company_search:" + ":".join(cache_parts) if cache_parts else "company_search:default"

        # 尝试从缓存获取
        try:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return Response(json.loads(cached_data))
        except Exception:
            pass

        # 缓存未命中，执行数据库查询并序列化
        response = super().list(request, *args, **kwargs)

        # 将结果存入缓存，过期时间为 300 秒（5 分钟）
        try:
            cache.set(cache_key, json.dumps(response.data), timeout=300)
        except Exception:
            pass

        return response


class CompanyStandardsView(generics.ListAPIView):
    """
    GET /api/client/search/companies/{id}/standards/
    展示企业名下的所有企标和团标（企业资产视图）
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StandardListSerializer
    pagination_class = None

    def get_queryset(self):
        from standards.models import Standard
        company_id = self.kwargs['pk']
        return Standard.objects.filter(
            company_id=company_id,
            type__in=['enterprise', 'group']
        ).order_by('-created_at')


class CompanyExportView(APIView):
    """
    GET /api/client/search/companies/export/
    导出当前检索结果为 Excel
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        params = request.query_params
        
        # 解析 LBS
        lat = params.get('lat')
        lng = params.get('lng')
        radius_km = params.get('radius_km')
        
        center_lat = None
        center_lng = None
        radius = None
        
        if lat and lng and radius_km:
            try:
                center_lat = float(lat)
                center_lng = float(lng)
                radius = float(radius_km)
            except ValueError:
                pass

        qs = services.search_companies(
            keyword=params.get('keyword', ''),
            province_id=params.get('province_id'),
            city_id=params.get('city_id'),
            district_id=params.get('district_id'),
            center_lat=center_lat,
            center_lng=center_lng,
            radius_km=radius,
            ics=params.get('ics', ''),
            ccs=params.get('ccs', ''),
            standard_logic=params.get('standard_logic', 'OR'),
        )

        excel_bytes = services.export_companies_to_excel(qs)
        response = HttpResponse(
            excel_bytes,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="search_results.xlsx"'
        return response


class ClientLeadCreateView(generics.CreateAPIView):
    """
    POST /api/client/leads/
    前台一键建档意向销售线索
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CompanyLeadSerializer
    queryset = CompanyLead.objects.all()

