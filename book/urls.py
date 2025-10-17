# book/urls.py

from django.urls import path
from . import views

app_name = 'book'

urlpatterns = [
    # Book List
    path('', views.book_list, name='book_list'),

    # Initiate Visa card payment (Consolidated and put in a single, appropriate place)
    path('pay/<int:book_id>/', views.pay_with_card, name='pay_with_card'), 
    
    # 💳 Payment callback handler (Using the clearer 'payment/callback/' path)
    path('payment/callback/', views.payment_callback, name='payment_callback'),

    # Book detail by ID
    path('<int:book_id>/', views.book_detail, name='book_detail'),

    # Upload a new book
    path('upload/', views.book_upload, name='book_upload'),

    # Teacher dashboard
    path('dashboard/', views.teacher_book_dashboard, name='teacher_book_dashboard'),

    # Edit a book
    path('edit/<int:book_id>/', views.edit_book, name='edit_book'),

    # Delete a book
    path('delete/<int:book_id>/', views.delete_book, name='delete_book'),

    # Download book securely
    path('download/<int:book_id>/', views.download_book, name='download_book'),

    # Airtel QR payment initiation (No change)
    path('book/airtel/callback/', views.initiate_airtel_payment, name='initiate_airtel_payment'),

    # Vendor earnings dashboard
    path('earnings/', views.vendor_earnings, name='vendor_earnings'),

    # Vendor analytics dashboard
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),

    # Fallback for missing/incomplete books
    path('missing/', views.book_missing, name='book_missing'),
]