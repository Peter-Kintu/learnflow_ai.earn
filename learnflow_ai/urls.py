from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# Import the 'home' view from the aiapp so it can be used for the root URL
from aiapp.views import home

urlpatterns = [
    # Admin site URL
    path('admin/', admin.site.urls),
    
    # User-related URLs (login, register, etc.) are now at the root level.
    # This means URLs will be like '/login' and '/register'.
    path('', include('user.urls')),
    
    # AI App-related URLs are also at the root level.
    path('', include('aiapp.urls')),

    # This line handles the root URL ('/') and directs it to the 'home' view.
    path('', home, name='root'),
    
    # Video and Book app URLs with their respective prefixes.
    path('video/', include('video.urls')),
    path('book/', include('book.urls')),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
