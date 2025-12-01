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
    changefreq = 'weekly'
    protocol = 'https'  # Ensures HTTPS links

    def items(self):
        # List the view names for all important static pages
        return [
            'aiapp:home',
            'aiapp:quiz_list',
            'video:video_list',
            'book:book_list',
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
    """Reusable base sitemap for models with created_at field."""
    changefreq = "monthly"
    protocol = 'https'

    def items(self):
        return self.model.objects.all().order_by('-created_at')

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        return reverse(self.detail_view_name, args=[obj.pk])


# ----------------------------------------------------------------------
# --- 3. Specific Model Sitemaps ---
# ----------------------------------------------------------------------
class QuizSitemap(BaseModelSitemap):
    """Sitemap for all Quiz objects."""
    priority = 0.8
    model = Quiz
    detail_view_name = 'aiapp:quiz_detail'


class BookSitemap(BaseModelSitemap):
    """Sitemap for all Book objects."""
    priority = 0.9
    model = Book
    detail_view_name = 'book:book_detail'


class VideoSitemap(BaseModelSitemap):
    """Sitemap for all Video objects."""
    priority = 0.8
    model = Video
    detail_view_name = 'video:video_detail'