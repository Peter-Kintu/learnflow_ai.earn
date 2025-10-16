from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from aiapp.views import sitemap_view
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap
from user.views import ping  # loading_screen now handled inside user.urls

urlpatterns = [
    # The admin site URL
    path('admin/', admin.site.urls),

    # Redirect root URL to login
    # path('', RedirectView.as_view(pattern_name='user:login', permanent=False), name='root'),

    # Serve robots.txt
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),

    # Include user app URLs (loading screen now handled here)
    path('', include('user.urls')),

    # Other apps
    path('aiapp/', include('aiapp.urls')),
    path('video/', include('video.urls')),
    path('book/', include('book.urls')),
    path('legal/', include('legalpages.urls')),

    # Sitemap
    path('sitemap.xml', sitemap_view, name='sitemap'),

    # Ping endpoint for wake-up detection
    path('ping/', ping, name='ping'),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)