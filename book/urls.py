# # book/urls.py

# from django.urls import path
# from . import views

# app_name = 'book'

# urlpatterns = [
#     path('', views.book_list, name='book_list'),
#     path('pay/<int:book_id>/', views.pay_with_card, name='pay_with_card'), 
#     path('payment/callback/', views.payment_callback, name='payment_callback'),
#     path('<int:book_id>/', views.book_detail, name='book_detail'),
#     path('upload/', views.book_upload, name='book_upload'),
#     path('dashboard/', views.teacher_book_dashboard, name='teacher_book_dashboard'),
#     path('edit/<int:book_id>/', views.edit_book, name='edit_book'),
#     path('delete/<int:book_id>/', views.delete_book, name='delete_book'),
#     path('download/<int:book_id>/', views.download_book, name='download_book'),
#     # NOTE: Changed from 'book/airtel/callback/' to 'airtel/callback/' for correct routing
#     path('airtel/callback/', views.initiate_airtel_payment, name='initiate_airtel_payment'),
#     path('earnings/', views.vendor_earnings, name='vendor_earnings'),
#     path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),
#     path('missing/', views.book_missing, name='book_missing'),
# ]