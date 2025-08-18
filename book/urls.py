# books/urls.py

from django.urls import path
from . import views

app_name = 'book'

urlpatterns = [
    # The main URL for the book app, which will display a list of all books
    path('', views.book_list, name='book_list'),
    
    # URL for the book detail page
    path('<int:book_id>/', views.book_detail, name='book_detail'),
    
    # URL for creating a new book
    path('upload/', views.book_upload, name='book_upload'),

    # URL for the teacher book dashboard
    path('dashboard/', views.teacher_book_dashboard, name='teacher_book_dashboard'),
    
    # URL for editing a book
    path('edit/<int:book_id>/', views.edit_book, name='edit_book'),

    # URL for deleting a book
    path('delete/<int:book_id>/', views.delete_book, name='delete_book'),
]
