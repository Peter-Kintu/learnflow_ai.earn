from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from user.views import ping

# Correct import for sitemap views
from django.contrib.sitemaps.views import sitemap, index

# Import your sitemap classes
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

    # Robots.txt for SEO
    path("robots.txt", TemplateView.as_view(
        template_name="robots.txt", content_type="text/plain"
    )),

    # Sitemap index and sections
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('sitemap-index.xml', index, {'sitemaps': sitemaps}, name='sitemap-index'),

    # Health check endpoint
    path('ping/', ping, name='ping'),

    # Root URL routed to user app
    path('', include('user.urls')),

    # Other app routes
    path('aiapp/', include('aiapp.urls')),
    path('video/', include('video.urls')),
    path('book/', include('book.urls')),
    path('legal/', include(('legalpages.urls', 'legalpages'), namespace='legalpages')),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)