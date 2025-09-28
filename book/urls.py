from django.urls import path
from . import views

app_name = 'book'

urlpatterns = [
    # List all books
    path('', views.book_list, name='book_list'),

    # Book detail by ID
    path('<int:book_id>/', views.book_detail, name='book_detail'),

    # Optional: Book detail by slug (SEO-friendly)
    # path('<slug:slug>/', views.book_detail_by_slug, name='book_detail_by_slug'),

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

    # Initiate Visa card payment
    path('pay/<int:book_id>/', views.pay_with_card, name='pay_with_card'),

    # Payment callback handler
    path('payment/callback/', views.payment_callback, name='payment_callback'),

    # Vendor earnings dashboard
    path('earnings/', views.vendor_earnings, name='vendor_earnings'),
]