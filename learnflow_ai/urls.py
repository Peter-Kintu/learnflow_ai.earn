from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from user.views import ping 

# FIX 1: Use the aliased import style to resolve the Pylance warning and keep the code clean.
# FIX 2: Removed direct import of 'sitemap' and the unused 'sitemap_view'.
from django.contrib.sitemaps import views as sitemap_views 

# Keep imports for your sitemap classes
from .sitemap import StaticSitemap, QuizSitemap, BookSitemap, VideoSitemap 

sitemaps = {
    'static': StaticSitemap,
    'quizzes': QuizSitemap,
    'books': BookSitemap,
    'videos': VideoSitemap,
}

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),

    # Serve robots.txt for SEO
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),

    # Serve sitemap for search engines
    # FIX 3: Removed the duplicate path and kept only the standard, Django-contrib path
    # using the corrected aliased view.
    path('sitemap.xml', sitemap_views.sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),

    # Health check endpoint for uptime monitoring
    path('ping/', ping, name='ping'),

    # Route root URL '/' to user.urls — loading_screen is served here
    path('', include('user.urls')),

    # Other app routes
    path('aiapp/', include('aiapp.urls')),
    path('video/', include('video.urls')),
    path('book/', include('book.urls')),
    path('legal/', include('legalpages.urls', namespace='legalpages')),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)