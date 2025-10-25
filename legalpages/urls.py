from django.urls import path
from . import views

# Setting app_name for URL namespacing
app_name = 'legalpages' 

urlpatterns = [
    # Static Pages 
    path('privacy/', views.privacy_policy, name='privacy'),
    path('terms/', views.terms_conditions, name='terms'),
    path('about/', views.about_us, name='about'),
    path('contact/', views.contact_us, name='contact'),
    path('sitemap-page/', views.sitemap_page, name='sitemap_page'),
    
    # Note: Using <str:video_id> is safer than <int:video_id> for YouTube IDs which are alphanumeric
    path('video/analyze/<str:video_id>/', views.video_analysis_view, name='video_analysis'),
    
    # Main Application Views
    path('overview/', views.learnflow_overview, name='overview'),
    path('', views.learnflow_video_analysis, name='learnflow_main'),
    
    # API Endpoints
    path('api/analyze_video/', views.analyze_video_api, name='api_analyze_video'),
    path('api/submit_quiz/', views.submit_quiz_api, name='api_submit_quiz'),
    # NEW: API endpoint for exporting content (PDF generation)
    path('api/export_content/', views.export_content_api, name='api_export_content'), 
]
