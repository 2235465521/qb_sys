import datetime
from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from rest_framework import generics, views, status
from rest_framework.response import Response
from rest_framework.permissions import BasePermission
from rest_framework.pagination import PageNumberPagination

from .models import UsageLog
from .serializers import UsageLogSerializer
from standards.models import Standard

AdminUser = get_user_model()

class IsSystemAdmin(BasePermission):
    """仅限系统超级管理员与普通管理员访问"""
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role in ('superadmin', 'admin')
        )


class UsageLogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 200


class UsageLogListView(generics.ListAPIView):
    """
    获取后台详细使用审计日志列表（支持多维度过滤和搜索）
    """
    permission_classes = [IsSystemAdmin]
    serializer_class = UsageLogSerializer
    pagination_class = UsageLogPagination

    def get_queryset(self):
        qs = UsageLog.objects.select_related('user').all()

        # 1. 模糊搜索用户名/姓名/IP地址
        keyword = self.request.query_params.get('keyword')
        if keyword:
            qs = qs.filter(
                Q(username__icontains=keyword) |
                Q(real_name__icontains=keyword) |
                Q(ip_address__icontains=keyword)
            )

        # 2. 匹配具体操作描述
        action = self.request.query_params.get('action')
        if action:
            qs = qs.filter(action=action)

        # 3. 匹配是否异常下载
        is_warning = self.request.query_params.get('is_warning')
        if is_warning is not None:
            if is_warning.lower() == 'true':
                qs = qs.filter(is_warning=True)
            elif is_warning.lower() == 'false':
                qs = qs.filter(is_warning=False)

        # 4. 时间范围过滤
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            try:
                dt_start = timezone.make_aware(datetime.datetime.strptime(start_date, "%Y-%m-%d"))
                qs = qs.filter(created_at__gte=dt_start)
            except ValueError:
                pass
        if end_date:
            try:
                # 结束时间增加到当天 23:59:59
                dt_end = timezone.make_aware(
                    datetime.datetime.strptime(end_date, "%Y-%m-%d") + 
                    datetime.timedelta(days=1) - 
                    datetime.timedelta(seconds=1)
                )
                qs = qs.filter(created_at__lte=dt_end)
            except ValueError:
                pass

        return qs


class StatisticsSummaryView(views.APIView):
    """
    获取宏观统计概览（累计次数、今日频次、日/周活跃率）
    """
    permission_classes = [IsSystemAdmin]

    def get(self, request):
        now = timezone.now()
        today_start = timezone.make_aware(datetime.datetime.combine(now.date(), datetime.time.min))
        week_start = today_start - datetime.timedelta(days=6)

        # 核心指标计算
        total_hits = UsageLog.objects.count()
        today_hits = UsageLog.objects.filter(created_at__gte=today_start).count()
        
        # 活跃唯一用户数
        active_users_today = UsageLog.objects.filter(
            created_at__gte=today_start
        ).exclude(username='Anonymous').values('user_id').distinct().count()

        active_users_week = UsageLog.objects.filter(
            created_at__gte=week_start
        ).exclude(username='Anonymous').values('user_id').distinct().count()

        # 系统注册用户总数 (AdminUser 表中角色非 client 的，或者全部？包含 client 的前台用户均算作总用户数)
        total_users = AdminUser.objects.count()

        # 计算活跃率
        dau_rate = round((active_users_today / total_users * 100), 1) if total_users > 0 else 0.0
        wau_rate = round((active_users_week / total_users * 100), 1) if total_users > 0 else 0.0

        # 限流警告累计次数
        total_warnings = UsageLog.objects.filter(is_warning=True).count()

        return Response({
            'total_hits': total_hits,
            'today_hits': today_hits,
            'active_users_today': active_users_today,
            'active_users_week': active_users_week,
            'total_users': total_users,
            'dau_rate': min(dau_rate, 100.0),
            'wau_rate': min(wau_rate, 100.0),
            'total_warnings': total_warnings,
        })


class StatisticsChartView(views.APIView):
    """
    获取图表分析所需数据（近15天活跃趋势折线图、活跃用户柱状图、24小时活跃时段、热搜词、最受关注标准）
    """
    permission_classes = [IsSystemAdmin]

    def get(self, request):
        now = timezone.now()
        
        # 1. 近 15 天使用活跃量趋势 (折线图数据)
        trend_data = []
        for i in range(14, -1, -1):
            date = (now - datetime.timedelta(days=i)).date()
            day_start = timezone.make_aware(datetime.datetime.combine(date, datetime.time.min))
            day_end = timezone.make_aware(datetime.datetime.combine(date, datetime.time.max))
            count = UsageLog.objects.filter(created_at__range=(day_start, day_end)).count()
            trend_data.append({
                'date': date.strftime('%m-%d'),
                'count': count
            })

        # 2. 活跃用户使用量前 8 名 (柱状图数据)
        top_users_qs = UsageLog.objects.exclude(
            username='Anonymous'
        ).values('username', 'real_name').annotate(
            count=Count('id')
        ).order_by('-count')[:8]
        top_users = [
            {
                'username': u['username'],
                'real_name': u['real_name'] or u['username'],
                'count': u['count']
            } for u in top_users_qs
        ]

        # 3. 24 小时活跃时段分布 (柱状图数据)
        # 为避免 MySQL 时区表缺失引发 500 错误，在 Python 端做安全时区转换和小时分布归类
        thirty_days_ago = now - datetime.timedelta(days=30)
        created_ats = UsageLog.objects.filter(
            created_at__gte=thirty_days_ago
        ).values_list('created_at', flat=True)

        hour_map = {}
        for dt in created_ats:
            try:
                local_dt = timezone.localtime(dt)
                hour = local_dt.hour
                hour_map[hour] = hour_map.get(hour, 0) + 1
            except Exception:
                pass

        hourly_distribution = []
        for hour in range(24):
            hourly_distribution.append({
                'hour': f"{hour:02d}:00",
                'count': hour_map.get(hour, 0)
            })

        # 4. 前台搜索关键词排行前 10 名
        hot_keywords_qs = UsageLog.objects.exclude(
            keyword=''
        ).values('keyword').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        hot_keywords = [
            {
                'keyword': k['keyword'],
                'count': k['count']
            } for k in hot_keywords_qs
        ]

        # 5. 最受关注企标前 5 名 (分析预览与下载操作)
        hot_standards_qs = UsageLog.objects.filter(
            action__in=['前台预览企标PDF', '前台下载企标PDF', '后台导入企标规范']
        ).exclude(
            target_id=''
        ).values('target_id').annotate(
            count=Count('id')
        ).order_by('-count')[:5]

        # 匹配获取标准的名称以展示给管理员
        hot_standards = []
        if hot_standards_qs:
            standard_ids = [item['target_id'] for item in hot_standards_qs if item['target_id'].isdigit()]
            standards_map = {
                str(s.id): f"{s.standard_no} ({s.title or '未命名'})" 
                for s in Standard.objects.filter(id__in=standard_ids)
            }
            
            for item in hot_standards_qs:
                tid = item['target_id']
                std_name = standards_map.get(tid, f"企标ID: {tid}")
                hot_standards.append({
                    'id': tid,
                    'title': std_name,
                    'count': item['count']
                })

        return Response({
            'trend': trend_data,
            'top_users': top_users,
            'hourly_distribution': hourly_distribution,
            'hot_keywords': hot_keywords,
            'hot_standards': hot_standards,
        })
