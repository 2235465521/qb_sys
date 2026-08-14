"""
companies.views.dict_views — 行政区划字典视图
"""

from rest_framework import generics, permissions
from companies.models import Province, City, District
from companies.serializers import ProvinceSerializer, CitySerializer, DistrictSerializer
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

@method_decorator(cache_page(86400 * 30), name='dispatch')
class ProvinceListView(generics.ListAPIView):
    """GET /api/admin/dict/provinces/ — 所有省份"""
    permission_classes = [permissions.AllowAny]
    serializer_class = ProvinceSerializer
    queryset = Province.objects.all()
    pagination_class = None  # 字典数据不分页

@method_decorator(cache_page(86400 * 30), name='dispatch')
class CityListView(generics.ListAPIView):
    """GET /api/admin/dict/cities/?province_id=1 — 城市列表（按省筛选）"""
    permission_classes = [permissions.AllowAny]
    serializer_class = CitySerializer
    pagination_class = None

    def get_queryset(self):
        province_id = self.request.query_params.get('province_id')
        qs = City.objects.all()
        if province_id:
            qs = qs.filter(province_id=province_id)
        return qs

@method_decorator(cache_page(86400 * 30), name='dispatch')
class DistrictListView(generics.ListAPIView):
    """GET /api/admin/dict/districts/?city_id=1 — 区县列表（按市筛选）"""
    permission_classes = [permissions.AllowAny]
    serializer_class = DistrictSerializer
    pagination_class = None

    def get_queryset(self):
        city_id = self.request.query_params.get('city_id')
        qs = District.objects.all()
        if city_id:
            qs = qs.filter(city_id=city_id)
        return qs


class CompanyCategoryListView(generics.ListAPIView):
    """GET /api/admin/dict/categories/ — 企业所有制分类与标签树字典"""
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_serializer_class(self):
        from companies.serializers import CompanyCategorySerializer
        return CompanyCategorySerializer

    def get_queryset(self):
        from companies.models import CompanyCategory
        qs = CompanyCategory.objects.filter(is_active=True).select_related('parent')
        parent_id = self.request.query_params.get('parent_id')
        category_type = self.request.query_params.get('category_type')
        if parent_id:
            qs = qs.filter(parent_id=parent_id)
        if category_type:
            qs = qs.filter(category_type=category_type)
        return qs.order_by('sort_order', 'id')

