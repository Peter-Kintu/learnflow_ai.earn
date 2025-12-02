from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

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
        # List the view names for all important static pages
        return [
            "aiapp:home",
            "aiapp:quiz_list",
            "video:video_list",
            "book:book_list",
        ]

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        # Static pages can use the current date or a hardcoded date
        return timezone.now()


# ----------------------------------------------------------------------
# --- 2. Base Class for Dynamic Content Sitemaps ---
# ----------------------------------------------------------------------
class BaseModelSitemap(Sitemap):
    """
    Reusable base sitemap for models.
    Handles missing created_at gracefully.
    """
    changefreq = "monthly"
    protocol = "https"

    model = None
    detail_view_name = None

    def items(self):
        qs = self.model.objects.all()
        # If created_at exists, order by it; otherwise just return all
        if hasattr(self.model, "created_at"):
            qs = qs.order_by("-created_at")
        return qs

    def lastmod(self, obj):
        # Use created_at if available, else updated_at, else now
        if hasattr(obj, "created_at"):
            return obj.created_at
        if hasattr(obj, "updated_at"):
            return obj.updated_at
        return timezone.now()

    def location(self, obj):
        try:
            return reverse(self.detail_view_name, args=[obj.pk])
        except Exception:
            # Fallback: return homepage if reverse fails
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