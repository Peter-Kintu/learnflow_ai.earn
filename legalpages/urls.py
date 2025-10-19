from django.urls import path
from . import views

# Setting app_name for URL namespacing
app_name = 'legalpages' 

urlpatterns = [
    # Static Pages (These pages are typically included in the project's root URLs)
    path('privacy/', views.privacy_policy, name='privacy'),
    path('terms/', views.terms_conditions, name='terms'),
    path('about/', views.about_us, name='about'),
    path('contact/', views.contact_us, name='contact'),
    path('sitemap-page/', views.sitemap_page, name='sitemap_page'),
    path('video/analyze/<int:video_id>/', views.video_analysis_view, name='video_analysis'),
    
    # Main Application Views
    path('overview/', views.learnflow_overview, name='overview'),
    path('', views.learnflow_video_analysis, name='learnflow_main'),
    
    # API Endpoint
    path('api/fetch_transcript/', views.fetch_transcript_api, name='api_fetch_transcript'),
]