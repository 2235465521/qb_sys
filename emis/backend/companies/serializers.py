"""
companies — 序列化器
"""

from rest_framework import serializers
from .models import Company, Province, City, District, CompanyLead


class ProvinceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Province
        fields = ['id', 'code', 'name']


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'code', 'name', 'province_id']


class DistrictSerializer(serializers.ModelSerializer):
    class Meta:
        model = District
        fields = ['id', 'code', 'name', 'city_id']


class CompanyListSerializer(serializers.ModelSerializer):
    """列表用（精简字段，减少传输量）"""
    province_name = serializers.CharField(source='province.name', read_only=True, default='')
    city_name = serializers.CharField(source='city.name', read_only=True, default='')
    district_name = serializers.CharField(source='district.name', read_only=True, default='')
    # LBS 检索时附带距离（可能为 None）
    distance_km = serializers.SerializerMethodField()
    standards_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'credit_code', 'legal_person',
            'province_name', 'city_name', 'district_name',
            'latitude', 'longitude', 'contact', 'status',
            'distance_km', 'standards_count', 'created_at',
        ]

    def get_distance_km(self, obj):
        meters = getattr(obj, 'distance_meters', None)
        if meters is not None:
            return round(meters / 1000, 2)
        return None


class CompanyDetailSerializer(serializers.ModelSerializer):
    """详情用（全字段）"""
    province = ProvinceSerializer(read_only=True)
    city = CitySerializer(read_only=True)
    district = DistrictSerializer(read_only=True)
    province_id = serializers.PrimaryKeyRelatedField(
        queryset=Province.objects.all(), source='province', write_only=True, required=False
    )
    city_id = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.all(), source='city', write_only=True, required=False
    )
    district_id = serializers.PrimaryKeyRelatedField(
        queryset=District.objects.all(), source='district', write_only=True, required=False
    )

    class Meta:
        model = Company
        fields = [
            'id', 'name', 'credit_code', 'legal_person',
            'province', 'city', 'district',
            'province_id', 'city_id', 'district_id',
            'latitude', 'longitude', 'contact', 'address',
            'status', 'is_deleted', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_deleted', 'created_at', 'updated_at']


class CompanyLeadSerializer(serializers.ModelSerializer):
    """B2B 意向销售线索序列化器"""
    company_name = serializers.CharField(source='company.name', read_only=True, default='')
    company_credit_code = serializers.CharField(source='company.credit_code', read_only=True, default='')
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CompanyLead
        fields = [
            'id', 'company', 'company_name', 'company_credit_code',
            'source', 'source_display',
            'contact_name', 'contact_phone', 'contact_wechat',
            'status', 'status_display', 'memo',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# 后台管理使用 Detail 序列化器
CompanySerializer = CompanyDetailSerializer

