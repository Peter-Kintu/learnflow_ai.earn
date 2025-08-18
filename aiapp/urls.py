# aiapp/urls.py

from django.urls import path
from . import views

app_name = 'aiapp'

urlpatterns = [
    # General app URLs
    path('', views.home, name='home'),
    
    # Quiz URLs
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quizzes/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quizzes/create/', views.create_quiz, name='create_quiz'),
    path('quizzes/<int:quiz_id>/attempt/', views.quiz_attempt, name='quiz_attempt'),
    path('quizzes/<int:quiz_id>/results/', views.quiz_results, name='quiz_results'),
    
    # User Profile URL
    path('profile/<int:user_id>/', views.user_profile, name='user_profile'),
]
