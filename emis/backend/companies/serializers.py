"""
companies — 序列化器
"""

from rest_framework import serializers
from .models import Company, Province, City, District


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
    standards_count = serializers.SerializerMethodField()

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

    def get_standards_count(self, obj):
        # 取 services.py 里已注解好的本地企标与团标数量，如果没有则实时获取（避免全局 annotate 导致的慢查询）
        local_count = getattr(obj, 'standards_count', None)
        if local_count is None:
            local_count = obj.standards.filter(type__in=['enterprise', 'group']).count()
        
        # 实时查询联邦外库获取此企业的国标/行标等数量
        federated_count = 0
        search_name = obj.name.strip()
        if search_name:
            from django.core.cache import cache
            cache_key = f"federated_std_count_{obj.id}"
            cached_count = cache.get(cache_key)
            if cached_count is not None:
                federated_count = cached_count
            else:
                from django.db import connections
                try:
                    with connections['stsc_db'].cursor() as cursor:
                        cursor.execute("SET NAMES utf8mb4;")
                        query = """
                            SELECT COUNT(DISTINCT v.std_id)
                            FROM unit_dict u
                            JOIN std_unit_relation r ON u.unit_id = r.unit_id
                            JOIN view_std_full v ON r.base_id = v.id
                            WHERE u.unit_name LIKE %s
                        """
                        search_param = f"%{search_name}%".encode('utf-8')
                        cursor.execute(query, [search_param])
                        row = cursor.fetchone()
                        if row:
                            federated_count = row[0]
                    # 将外部数据库的查询结果缓存一天
                    cache.set(cache_key, federated_count, timeout=86400)
                except Exception:
                    pass
                
        return local_count + federated_count


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
            # 16个新增详细字段
            'established_date', 'registered_address', 'registered_zipcode',
            'valid_mobile', 'more_phones', 'email', 'company_type',
            'registration_no', 'organization_code', 'industry_category',
            'industry_major', 'industry_middle', 'industry_minor',
            'company_size', 'english_name', 'former_names',
        ]
        read_only_fields = ['id', 'is_deleted', 'created_at', 'updated_at']


from .models import Company, Province, City, District, Lead, FollowUp, Attachment, LeadOption


class LeadOptionSerializer(serializers.ModelSerializer):
    """线索自定义配置参数序列化器"""
    class Meta:
        model = LeadOption
        fields = ['id', 'option_type', 'name', 'value', 'is_active', 'sort_order']


class AttachmentSerializer(serializers.ModelSerializer):
    """线索附件序列化器"""
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ['id', 'file', 'filename', 'size', 'file_url', 'created_at']
        read_only_fields = ['id', 'filename', 'size', 'created_at']

    def get_file_url(self, obj):
        if obj.file:
            from django.conf import settings
            backend_url = getattr(settings, 'BACKEND_URL', '')
            # 如果在 settings 里明确配置了非本地的 BACKEND_URL，优先使用它，防止 Nginx 反代理丢端口
            if backend_url and '127.0.0.1' not in backend_url and 'localhost' not in backend_url:
                return f"{backend_url.rstrip('/')}{obj.file.url}"

            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)

            fallback = backend_url or 'http://127.0.0.1:8000'
            return f"{fallback.rstrip('/')}{obj.file.url}"
        return None


class FollowUpSerializer(serializers.ModelSerializer):
    """线索跟进动态时间轴序列化器"""
    creator_name = serializers.CharField(source='creator.username', read_only=True, default='')

    class Meta:
        model = FollowUp
        fields = ['id', 'lead', 'content', 'created_at', 'creator', 'creator_name']
        read_only_fields = ['id', 'created_at', 'creator']


class LeadSerializer(serializers.ModelSerializer):
    """线索合并序列化器（包含跟进记录和附件）"""
    enterprise_name = serializers.CharField(source='enterprise.name', read_only=True, default='')
    enterprise_credit_code = serializers.CharField(source='enterprise.credit_code', read_only=True, default='')
    
    # 负责人为字符串字段
    assignee = serializers.CharField(required=False, allow_blank=True, allow_null=True, default='')
    assignee_name = serializers.CharField(source='assignee', read_only=True, default='')
    
    source_display = serializers.SerializerMethodField()
    req_type_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    followups = FollowUpSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Lead
        fields = [
            'id', 'source', 'source_display', 'req_type', 'req_type_display',
            'status', 'status_display', 'assignee', 'assignee_name',
            'enterprise', 'enterprise_name', 'enterprise_credit_code',
            'contact_name', 'contact_phone', 'contact_wechat',
            'followups', 'attachments', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_option_label(self, option_type, value):
        if not value:
            return ''
        
        # 使用实例级缓存，避免序列化列表时的 N+1 查询问题
        if not hasattr(self, '_options_map'):
            options = LeadOption.objects.filter(is_active=True)
            self._options_map = {}
            for opt in options:
                self._options_map[(opt.option_type, opt.value)] = opt.name
                
        label = self._options_map.get((option_type, value))
        if label:
            return label
            
        # 降级退回至硬编码默认配置值
        defaults = {
            'source': dict(Lead.DEFAULT_SOURCE_CHOICES),
            'req_type': dict(Lead.DEFAULT_REQ_TYPE_CHOICES),
            'status': dict(Lead.DEFAULT_STATUS_CHOICES),
        }
        return defaults.get(option_type, {}).get(value, value)

    def get_source_display(self, obj):
        return self.get_option_label('source', obj.source)

    def get_req_type_display(self, obj):
        return self.get_option_label('req_type', obj.req_type)

    def get_status_display(self, obj):
        return self.get_option_label('status', obj.status)


# 后台管理使用 Detail 序列化器
CompanySerializer = CompanyDetailSerializer

