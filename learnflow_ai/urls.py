# project/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include the URLs from the 'aiapp' application
    path('', include('aiapp.urls')),
    # Include the URLs from the 'video' application
    path('video/', include('video.urls')),
    # Include the URLs from the new 'books' application
    path('book/', include('book.urls')),
    
    # This line is crucial. It tells Django where to find the login,
    # logout, and registration URLs.
    path('user/', include('user.urls')),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

