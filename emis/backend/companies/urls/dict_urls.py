from django.urls import path
from companies.views.dict_views import (
    ProvinceListView, CityListView, DistrictListView, CompanyCategoryListView
)

urlpatterns = [
    path('provinces/', ProvinceListView.as_view(), name='dict-provinces'),
    path('cities/', CityListView.as_view(), name='dict-cities'),
    path('districts/', DistrictListView.as_view(), name='dict-districts'),
    path('categories/', CompanyCategoryListView.as_view(), name='dict-categories'),
]
