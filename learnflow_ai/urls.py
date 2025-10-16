from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from aiapp.views import sitemap_view
from user.views import ping  # loading_screen is served at root via user.urls

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),

    # Serve robots.txt for SEO
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),

    # Serve sitemap for search engines
    path('sitemap.xml', sitemap_view, name='sitemap'),

    # Health check endpoint for uptime monitoring
    path('ping/', ping, name='ping'),

    # Route root URL '/' to user.urls — loading_screen is served here
    path('', include('user.urls')),

    # Other app routes
    path('aiapp/', include('aiapp.urls')),
    path('video/', include('video.urls')),
    path('book/', include('book.urls')),
    path('legal/', include('legalpages.urls')),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)