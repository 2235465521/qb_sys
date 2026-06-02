"""
standards — 序列化器
"""

from rest_framework import serializers
from .models import Standard, NormativeReference
from companies.serializers import CompanyListSerializer


class NormativeReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NormativeReference
        fields = ['id', 'cited_standard_no', 'latest_standard_no']


class StandardListSerializer(serializers.ModelSerializer):
    """列表用（精简）"""
    company_name = serializers.CharField(source='company.name', read_only=True, default='')
    company_detail = CompanyListSerializer(source='company', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    pdf_url = serializers.SerializerMethodField()
    normative_references = NormativeReferenceSerializer(many=True, read_only=True)
    snippet = serializers.SerializerMethodField()
    is_parsed = serializers.SerializerMethodField()

    class Meta:
        model = Standard
        fields = [
            'id', 'standard_no', 'clean_id', 'type', 'type_display',
            'title', 'company_name', 'company_detail', 'ics', 'ccs', 'is_parsed', 'citation_count',
            'status', 'status_display', 'publish_date', 'created_at', 'pdf_url', 'normative_references',
            'snippet',
        ]

    def get_pdf_url(self, obj):
        if obj.disk_filename or obj.pdf_file:
            request = self.context.get('request')
            token_str = ""
            if request and request.auth:
                token_str = f"?token={str(request.auth)}"
            url = f"/api/client/standards/{obj.id}/download/{token_str}"
            return url
        return None

    def get_snippet(self, obj):
        return getattr(obj, 'snippet', None)

    def get_is_parsed(self, obj):
        if obj.is_parsed == 'indicators_parsed':
            return 'indicators_parsed'
        if 'normative_references' in getattr(obj, '_prefetched_objects_cache', {}):
            has_refs = len(obj.normative_references.all()) > 0
        else:
            has_refs = obj.normative_references.exists()
        if has_refs:
            return 'references_parsed'
        if obj.is_parsed in ('references_parsed', 'True', '1', True):
            return 'references_parsed'
        return 'unparsed'



class StandardDetailSerializer(serializers.ModelSerializer):
    """详情用（全字段，含链条和引用）"""
    company_name = serializers.CharField(source='company.name', read_only=True, default='')
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    pdf_url = serializers.SerializerMethodField()
    is_parsed = serializers.SerializerMethodField()

    class Meta:
        model = Standard
        fields = [
            'id', 'standard_no', 'clean_id', 'type', 'type_display',
            'title', 'company_name', 'ics', 'ccs',
            'pdf_url', 'is_parsed', 'citation_count',
            'all_chain', 'part_chain',
            'status', 'status_display',
            'publish_date', 'implement_date',
            'created_at', 'updated_at',
        ]

    def get_pdf_url(self, obj):
        if obj.disk_filename or obj.pdf_file:
            request = self.context.get('request')
            token_str = ""
            if request and request.auth:
                token_str = f"?token={str(request.auth)}"
            url = f"/api/client/standards/{obj.id}/download/{token_str}"
            return url
        return None

    def get_is_parsed(self, obj):
        if obj.is_parsed == 'indicators_parsed':
            return 'indicators_parsed'
        if 'normative_references' in getattr(obj, '_prefetched_objects_cache', {}):
            has_refs = len(obj.normative_references.all()) > 0
        else:
            has_refs = obj.normative_references.exists()
        if has_refs:
            return 'references_parsed'
        if obj.is_parsed in ('references_parsed', 'True', '1', True):
            return 'references_parsed'
        return 'unparsed'
