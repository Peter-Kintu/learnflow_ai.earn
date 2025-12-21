from django.contrib.sitemaps import Sitemap
from django.urls import reverse

# Absolute imports to avoid ModuleNotFoundError
from aiapp.models import Quiz
from book.models import Book
from video.models import Video


# ----------------------------------------------------------------------
# --- 1. Static Pages Sitemap ---
# ----------------------------------------------------------------------
class StaticSitemap(Sitemap):
    """Sitemap for fixed, unchanging pages."""
    priority = 1.0
    changefreq = "weekly"
    protocol = "https"

    def items(self):
        return [
            "aiapp:home",
            "aiapp:quiz_list",
            "video:video_list",
            "book:book_list",
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return None  # static pages rarely change


# ----------------------------------------------------------------------
# --- 2. Base Class for Dynamic Content Sitemaps ---
# ----------------------------------------------------------------------
class BaseModelSitemap(Sitemap):
    """
    Reusable base sitemap for models.
    Filters out inactive, redirected, or noindex pages if fields exist.
    """
    changefreq = "weekly"
    protocol = "https"

    model = None
    detail_view_name = None

    def items(self):
        qs = self.model.objects.all()

        # Filter out objects that shouldn't be indexed
        if hasattr(self.model, "is_active"):
            qs = qs.filter(is_active=True)
        if hasattr(self.model, "noindex"):
            qs = qs.filter(noindex=False)
        if hasattr(self.model, "redirect_url"):
            qs = qs.filter(redirect_url__isnull=True)

        # Order by created_at if available
        if hasattr(self.model, "created_at"):
            qs = qs.order_by("-created_at")

        return qs

    def lastmod(self, obj):
        if hasattr(obj, "updated_at") and obj.updated_at:
            return obj.updated_at
        if hasattr(obj, "created_at") and obj.created_at:
            return obj.created_at
        return None

    def location(self, obj):
        try:
            return reverse(self.detail_view_name, args=[obj.pk])
        except Exception:
            return reverse("aiapp:home")


# ----------------------------------------------------------------------
# --- 3. Specific Model Sitemaps ---
# ----------------------------------------------------------------------
class QuizSitemap(BaseModelSitemap):
    """Sitemap for all Quiz objects."""
    priority = 0.8
    model = Quiz
    detail_view_name = "aiapp:quiz_detail"


class BookSitemap(BaseModelSitemap):
    """Sitemap for all Book objects."""
    priority = 0.9
    model = Book
    detail_view_name = "book:book_detail"


class VideoSitemap(BaseModelSitemap):
    """Sitemap for all Video objects."""
    priority = 0.8
    model = Video
    detail_view_name = "video:video_detail"