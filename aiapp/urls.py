from django.urls import path
from . import views

# Set the application namespace for use with `{% url 'aiapp:name' %}`
app_name = 'aiapp'

urlpatterns = [
    # General app URLs
    path('', views.home, name='home'),
    
    # Student-facing Quiz URLs
    path('quizzes/', views.quiz_list, name='quiz_list'),
    path('quizzes/<int:quiz_id>/', views.quiz_detail, name='quiz_detail'),
    path('quizzes/<int:quiz_id>/attempt/', views.quiz_attempt, name='quiz_attempt'),
    path('quizzes/<int:quiz_id>/results/', views.quiz_results, name='quiz_results'),
    
    # Teacher Quiz Management URLs
    # This dashboard lists quizzes created by the logged-in teacher.
    path('quizzes/dashboard/', views.teacher_quiz_dashboard, name='teacher_quiz_dashboard'),
    # This URL allows teachers to edit a specific quiz.
    path('quizzes/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    # This URL handles the deletion of a specific quiz.
    path('quizzes/<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),
    path('quizzes/create/', views.create_quiz, name='create_quiz'),
    path('quizzes/report/', views.quiz_report, name='quiz_report'),
    
    # User Profile URL
    path('profile/<int:user_id>/', views.user_profile, name='user_profile'),
]