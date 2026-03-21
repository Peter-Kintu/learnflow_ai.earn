from django.urls import path
from . import views

app_name = 'school'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('fees/', views.fees_list, name='fees_list'),
    path('farm/', views.farm_list, name='farm_list'),
    path('piggery/', views.piggery_list, name='piggery_list'),
    path('local-chicken/', views.local_chicken_list, name='local_chicken_list'),
    path('expenses/', views.expense_list, name='expense_list'),
    path('delete/<str:model_type>/<int:pk>/', views.delete_record, name='delete_record'),
]