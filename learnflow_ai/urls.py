from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.views.generic.base import RedirectView   # ✅ add this import
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

    # ✅ Redirect old paths to new ones (fixes 404s)
    path("quiz/<int:quiz_id>/", RedirectView.as_view(pattern_name="aiapp:quiz_detail", permanent=True)),
    path("books/<int:book_id>/", RedirectView.as_view(pattern_name="book:book_detail", permanent=True)),
    path("videos/<int:video_id>/", RedirectView.as_view(pattern_name="video:video_detail", permanent=True)),

    # Root URL routed to user app
    path("", include("user.urls")),

    # Other app routes
    path("aiapp/", include("aiapp.urls")),
    path("video/", include("video.urls")),
    path("book/", include("book.urls")),
    path("legal/", include(("legalpages.urls", "legalpages"), namespace="legalpages")),
]

# Serve static and media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)