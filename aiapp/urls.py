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
    path('quizzes/results/<int:attempt_id>/', views.quiz_results, name='quiz_results'),
    path('quizzes/review/<int:attempt_id>/', views.quiz_review, name='quiz_review'),
    
    # Teacher Quiz Management URLs
    path('quizzes/dashboard/', views.teacher_quiz_dashboard, name='teacher_quiz_dashboard'),
    path('quizzes/create/', views.create_quiz, name='create_quiz'),
    path('quizzes/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('quizzes/<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),
    # This URL for the quiz report now correctly expects a quiz ID.
    path('quizzes/report/<int:quiz_id>/', views.quiz_report, name='quiz_report'),
    
    # User Profile URL
    path('profile/<int:user_id>/', views.user_profile, name='user_profile'),
]
