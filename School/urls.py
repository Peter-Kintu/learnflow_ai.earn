from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('fees/', views.fees_list, name='fees_list'),
    path('farm/', views.farm_list, name='farm_list'),
]