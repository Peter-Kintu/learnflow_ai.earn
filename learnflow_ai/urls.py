from django.contrib import admin
from django.urls import path, include
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from aiapp.views import sitemap_view
from django.views.generic import TemplateView
from django.contrib.sitemaps.views import sitemap


urlpatterns = [
    # The admin site URL
    path('admin/', admin.site.urls),
    
    # This line redirects the root URL ('/') to the login URL.
    # This ensures that the first page the user sees is the login page.
    path('', RedirectView.as_view(pattern_name='user:login', permanent=False), name='root'),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    
    # This includes the URLs from the 'user' app, making them available at the root level.
    # For example, the login page will be at /login/ and the register page at /register/.
    path('', include('user.urls')),
    
    # The other apps are included with a prefix for clearer organization.
    path('aiapp/', include('aiapp.urls')),
    path('video/', include('video.urls')),
    path('book/', include('book.urls')),
    path('sitemap.xml', sitemap_view, name='sitemap'),
    path('', include('legalpages.urls')),
    
]

# This is for serving static and media files during development.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
