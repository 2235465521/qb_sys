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
            # 16个新增详细字段
            'established_date', 'registered_address', 'registered_zipcode',
            'valid_mobile', 'more_phones', 'email', 'company_type',
            'registration_no', 'organization_code', 'industry_category',
            'industry_major', 'industry_middle', 'industry_minor',
            'company_size', 'english_name', 'former_names',
        ]
        read_only_fields = ['id', 'is_deleted', 'created_at', 'updated_at']


from .models import Company, Province, City, District, Lead, FollowUp, Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    """线索附件序列化器"""
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = ['id', 'file', 'filename', 'size', 'file_url', 'created_at']
        read_only_fields = ['id', 'filename', 'size', 'created_at']

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
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
    assignee_name = serializers.CharField(source='assignee.username', read_only=True, default='')
    
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    req_type_display = serializers.CharField(source='get_req_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
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


# 后台管理使用 Detail 序列化器
CompanySerializer = CompanyDetailSerializer

