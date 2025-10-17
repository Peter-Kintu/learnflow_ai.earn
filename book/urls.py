# book/urls.py

from django.urls import path
from . import views

app_name = 'book'

urlpatterns = [
    # Book List (Example: /book/)
    path('', views.book_list, name='book_list'),

    # Initiate Visa card payment (Example: /book/pay/1/)
    path('pay/<int:book_id>/', views.pay_with_card, name='pay_with_card'), 
    
    # 💳 Payment callback handler - This is the definitive path for the payment gateway to hit.
    # (Example: /book/payment/callback/)
    path('payment/callback/', views.payment_callback, name='payment_callback'),

    # Book detail by ID (Example: /book/1/)
    path('<int:book_id>/', views.book_detail, name='book_detail'),

    # Upload a new book (Example: /book/upload/)
    path('upload/', views.book_upload, name='book_upload'),

    # Teacher dashboard (Example: /book/dashboard/)
    path('dashboard/', views.teacher_book_dashboard, name='teacher_book_dashboard'),

    # Edit a book (Example: /book/edit/1/)
    path('edit/<int:book_id>/', views.edit_book, name='edit_book'),

    # Delete a book (Example: /book/delete/1/)
    path('delete/<int:book_id>/', views.delete_book, name='delete_book'),

    # Download book securely (Example: /book/download/1/)
    path('download/<int:book_id>/', views.download_book, name='download_book'),

    # Airtel QR payment initiation (Example: /book/airtel/callback/)
    # NOTE: Changed from 'book/airtel/callback/' to 'airtel/callback/' for correct routing
    path('airtel/callback/', views.initiate_airtel_payment, name='initiate_airtel_payment'),

    # Vendor earnings dashboard (Example: /book/earnings/)
    path('earnings/', views.vendor_earnings, name='vendor_earnings'),

    # Vendor analytics dashboard (Example: /book/vendor/dashboard/)
    path('vendor/dashboard/', views.vendor_dashboard, name='vendor_dashboard'),

    # Fallback for missing/incomplete books (Example: /book/missing/)
    path('missing/', views.book_missing, name='book_missing'),
]