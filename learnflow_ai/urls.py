from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView   # ✅ needed for redirects
from django.http import HttpResponse
from user.views import ping

# Correct import for sitemap views
from django.contrib.sitemaps.views import sitemap, index

# Import your sitemap classes
from .sitemap import StaticSitemap, QuizSitemap, VideoSitemap

sitemaps = {
    'static': StaticSitemap,
    'quizzes': QuizSitemap,
    'videos': VideoSitemap,
}

urlpatterns = [
    # Google Search Console verification file
    path(
        "googled5b56ec94e5b9cb2.html",
        TemplateView.as_view(template_name="googled5b56ec94e5b9cb2.html"),
    ),

    # Admin interface
    path("admin/", admin.site.urls),

    # Robots.txt for SEO
    path(
        "robots.txt",
        TemplateView.as_view(template_name="robots.txt", content_type="text/plain"),
    ),

    # Sitemap index and sections
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("sitemap-index.xml", index, {"sitemaps": sitemaps}, name="sitemap-index"),

    # Health check endpoint
    path("ping/", ping, name="ping"),

    # HTTP fallback for the live-teacher WebSocket path so diagnostics are visible in the browser
    path(
        "ws/live-teacher/",
        lambda request: HttpResponse(
            "This endpoint is reserved for WebSocket connections to /ws/live-teacher/.\n"
            "If you see this page in a browser, the websocket server is reachable over HTTP, "
            "but the client must connect using ws:// or wss://.\n"
            "If this returns 404 in production, verify your ASGI/WebSocket proxy and Daphne routing.",
            content_type="text/plain",
        ),
        name="ws_live_teacher_fallback",
    ),

    # ✅ Redirect old paths to new ones (fixes 404s and NoReverseMatch)
    path("quiz/<int:quiz_id>/", RedirectView.as_view(pattern_name="aiapp:quiz_detail", permanent=True)),
    path("videos/<int:video_id>/", RedirectView.as_view(pattern_name="video:video_detail", permanent=True)),

    # Root URL routed to user app
    path("", include("user.urls")),

    # Other app routes
    path("aiapp/", include("aiapp.urls")),
    path("video/", include("video.urls")),
    path("legal/", include(("legalpages.urls", "legalpages"), namespace="legalpages")),
    path("school/", include(("School.urls", "school"), namespace="school")),
  
    
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)