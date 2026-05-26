"""
users — 视图、序列化器
"""

from rest_framework import generics, serializers, permissions, viewsets
from rest_framework.pagination import PageNumberPagination
from .models import Member, OrganizationCategory, MemberOrgRole


class OrganizationCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizationCategory
        fields = ['id', 'name', 'code', 'is_system', 'created_at']
        read_only_fields = ['id', 'is_system', 'created_at']


class MemberOrgRoleSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_code = serializers.CharField(source='category.code', read_only=True)

    class Meta:
        model = MemberOrgRole
        fields = ['id', 'category', 'category_name', 'category_code', 'org_name', 'position']
        read_only_fields = ['id']


class MemberSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    roles = MemberOrgRoleSerializer(many=True, read_only=True)

    class Meta:
        model = Member
        fields = ['id', 'name', 'company', 'phone', 'status', 'status_display', 'notes', 'roles', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def create(self, validated_data):
        roles_data = self.context['request'].data.get('roles', [])
        member = Member.objects.create(**validated_data)
        for r_data in roles_data:
            category_id = r_data.get('category')
            if category_id:
                MemberOrgRole.objects.create(
                    member=member,
                    category_id=category_id,
                    org_name=r_data.get('org_name', ''),
                    position=r_data.get('position', '')
                )
        return member

    def update(self, instance, validated_data):
        roles_data = self.context['request'].data.get('roles', None)
        instance = super().update(instance, validated_data)
        if roles_data is not None:
            # Re-sync roles
            instance.roles.all().delete()
            for r_data in roles_data:
                category_id = r_data.get('category')
                if category_id:
                    MemberOrgRole.objects.create(
                        member=instance,
                        category_id=category_id,
                        org_name=r_data.get('org_name', ''),
                        position=r_data.get('position', '')
                    )
        return instance


class MemberPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


# 前台会员列表/创建
class MemberListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MemberSerializer
    pagination_class = MemberPagination

    def get_queryset(self):
        qs = Member.objects.prefetch_related('roles__category').all()
        status = self.request.query_params.get('status')
        keyword = self.request.query_params.get('keyword')
        category_code = self.request.query_params.get('category_code')

        if status:
            qs = qs.filter(status=status)
        if category_code:
            qs = qs.filter(roles__category__code=category_code)
        if keyword:
            from django.db.models import Q
            qs = qs.filter(
                Q(name__icontains=keyword) |
                Q(phone__icontains=keyword) |
                Q(roles__org_name__icontains=keyword) |
                Q(roles__position__icontains=keyword)
            ).distinct()
        return qs


class MemberDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = MemberSerializer
    queryset = Member.objects.all()


class OrganizationCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrganizationCategorySerializer
    queryset = OrganizationCategory.objects.all()
    pagination_class = None

    def perform_destroy(self, instance):
        if instance.is_system:
            raise serializers.ValidationError("系统预置分类模块不允许删除！")
        super().perform_destroy(instance)


# 后台会员管理（相同逻辑，可扩展更多权限）
MemberAdminListCreateView = MemberListCreateView
MemberAdminDetailView = MemberDetailView


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.http import HttpResponse
import openpyxl
import io

class UserInfoView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'username': user.username,
            'real_name': user.real_name,
            'role': user.role,
            'is_superuser': user.is_superuser
        })


class UserRegisterView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        real_name = request.data.get('real_name', '')
        
        if not username:
            return Response({'detail': '用户名不能为空'}, status=status.HTTP_400_BAD_REQUEST)
        if len(username) < 2:
            return Response({'detail': '用户名长度至少为2位'}, status=status.HTTP_400_BAD_REQUEST)
            
        from users.models import AdminUser
        if AdminUser.objects.filter(username=username).exists():
            return Response({'detail': '该用户名已被注册'}, status=status.HTTP_400_BAD_REQUEST)
            
        # Create user with fixed password and 'client' role
        user = AdminUser.objects.create_user(
            username=username, 
            password='zkbz2026', 
            real_name=real_name,
            role='client'
        )
        return Response({'detail': '注册成功', 'username': user.username}, status=status.HTTP_201_CREATED)


class MemberExportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        fields = request.data.get('fields', [])
        if not fields or not isinstance(fields, list):
            return Response({'error': '请选择要导出的字段'}, status=status.HTTP_400_BAD_REQUEST)

        # 字段汉化对齐
        FIELD_MAP = {
            'name': '姓名',
            'phone': '联系电话',
            'position': '职务',
            'company': '归属单位/组织',
            'notes': '备注说明',
            'created_at': '入库时间'
        }

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "会员自定义数据表"

        # 写入表头
        headers = [FIELD_MAP.get(f, f) for f in fields]
        ws.append(headers)

        # 获取数据（提取前台或后台的过滤查询条件，方便过滤后导出）
        keyword = request.query_params.get('keyword')
        status_val = request.query_params.get('status')
        category_code = request.query_params.get('category_code')

        qs = Member.objects.prefetch_related('roles__category').all()
        if status_val:
            qs = qs.filter(status=status_val)
        if category_code:
            qs = qs.filter(roles__category__code=category_code)
        if keyword:
            from django.db.models import Q
            qs = qs.filter(
                Q(name__icontains=keyword) |
                Q(phone__icontains=keyword) |
                Q(roles__org_name__icontains=keyword) |
                Q(roles__position__icontains=keyword)
            ).distinct()

        # 写入数据行
        for m in qs:
            row_data = []
            for field in fields:
                if field == 'name':
                    row_data.append(m.name)
                elif field == 'phone':
                    row_data.append(m.phone)
                elif field == 'position':
                    roles = m.roles.all()
                    positions = [r.position for r in roles if r.position]
                    row_data.append(", ".join(positions) if positions else '')
                elif field == 'company':
                    row_data.append(m.company)
                elif field == 'notes':
                    row_data.append(m.notes)
                elif field == 'created_at':
                    row_data.append(m.created_at.strftime('%Y-%m-%d %H:%M:%S') if m.created_at else '')
                else:
                    row_data.append('')
            ws.append(row_data)

        # 转换为内存中的字节流
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename=members_export.xlsx'
        return response


# ── 管理后台：用户管理 (AdminUser ViewSet) ────────────────────────
from rest_framework.permissions import BasePermission
from users.models import AdminUser

class IsSystemAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ('superadmin', 'admin')

class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, min_length=2)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = AdminUser
        fields = ['id', 'username', 'real_name', 'role', 'role_display', 'is_active', 'created_at', 'password']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = AdminUser.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_password('zkbz2026')
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user

class AdminUserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsSystemAdmin]
    serializer_class = AdminUserSerializer

    def get_queryset(self):
        qs = AdminUser.objects.all().order_by('-created_at')
        keyword = self.request.query_params.get('keyword')
        if keyword:
            from django.db.models import Q
            qs = qs.filter(Q(username__icontains=keyword) | Q(real_name__icontains=keyword))
        return qs
