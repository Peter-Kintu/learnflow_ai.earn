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
    path('quizzes/review/<int:attempt_id>/', views.quiz_review, name='review_answers'),

      # API endpoint for the chat feature
    # path('api/chat', views.chat_api, name='chat_api'),

    # API endpoint for the feedback feature
    # path('api/feedback', views.feedback_api, name='feedback_api'),
    
    # Teacher Quiz Management URLs
    path('quizzes/dashboard/', views.teacher_quiz_dashboard, name='teacher_quiz_dashboard'),
    path('quizzes/create/', views.create_quiz, name='create_quiz'),
    path('quizzes/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('quizzes/<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),
    # This URL for the quiz report now correctly expects a quiz ID.
    path('quizzes/report/quiz/<int:quiz_id>/', views.quiz_report_pdf_for_quiz, name='quiz_report_pdf_for_quiz'),
    # This URL is needed for the "Download Report" button on the results page.
    path('quizzes/report/attempt/<int:attempt_id>/', views.quiz_report_pdf_for_attempt, name='quiz_report_pdf_for_attempt'),
    path('quizzes/report/attempt/<int:attempt_id>/word/', views.quiz_report_word_for_attempt, name='quiz_report_word_for_attempt'),
    path('quizzes/<int:quiz_id>/retake/', views.retake_quiz, name='retake_quiz'),
    # User Profile URL
    path('profile/<int:user_id>/', views.user_profile, name='user_profile'),
    path('why-learnflow-ai/', views.why_learnflow_ai, name='why_learnflow_ai'),
]
