"""
users.urls.member_admin_urls — 后台会员管理路由
"""

from django.urls import path
from users.views import MemberAdminListCreateView, MemberAdminDetailView, MemberExportView

urlpatterns = [
    path('export/', MemberExportView.as_view(), name='admin-member-export'),
    path('', MemberAdminListCreateView.as_view(), name='admin-member-list'),
    path('<int:pk>/', MemberAdminDetailView.as_view(), name='admin-member-detail'),
]
