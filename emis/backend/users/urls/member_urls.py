from django.urls import path, include
from rest_framework.routers import DefaultRouter
from users.views import MemberListCreateView, MemberDetailView, OrganizationCategoryViewSet, MemberExportView

router = DefaultRouter()
router.register('categories', OrganizationCategoryViewSet, basename='member-categories')

urlpatterns = [
    path('export/', MemberExportView.as_view(), name='client-member-export'),
    path('', MemberListCreateView.as_view(), name='client-member-list'),
    path('<int:pk>/', MemberDetailView.as_view(), name='client-member-detail'),
    path('', include(router.urls)),
]
