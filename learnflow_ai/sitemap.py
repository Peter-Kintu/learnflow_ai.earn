from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

# Assuming Quiz model is in the 'aiapp'
from aiapp.models import Quiz 
from book.models import Book 
from video.models import Video 

# --- 1. Static Pages Sitemap ---
class StaticSitemap(Sitemap):
    """Sitemap for fixed, unchanging pages."""
    priority = 1.0
    changefreq = 'weekly'

    def items(self):
        return ['aiapp:home', 'aiapp:quiz_list', 'video:video_list', 'book:book_list'] 

    def location(self, item):
        return reverse(item)
    
    def lastmod(self, item):
        return timezone.now()

# ----------------------------------------------------------------------
# --- 2. Dynamic Content Sitemaps ---
# ----------------------------------------------------------------------

class QuizSitemap(Sitemap):
    """Sitemap for all Quiz objects."""
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        # FIX: Changed to order_by('-created_at')
        return Quiz.objects.all().order_by('-created_at')

    def lastmod(self, obj):
        # FIX: Changed to obj.created_at
        return obj.created_at 

    def location(self, obj):
        return reverse('aiapp:quiz_detail', args=[obj.pk])

class BookSitemap(Sitemap):
    """Sitemap for all Book objects."""
    changefreq = "monthly"
    priority = 0.9

    def items(self):
        # FIX: Changed to order_by('-created_at')
        return Book.objects.all().order_by('-created_at')

    def lastmod(self, obj):
        # FIX: Changed to obj.created_at
        return obj.created_at 

    def location(self, obj):
        return reverse('book:book_detail', args=[obj.pk])

class VideoSitemap(Sitemap):
    """Sitemap for all Video objects."""
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        # FIX: Changed to order_by('-created_at')
        return Video.objects.all().order_by('-created_at')

    def lastmod(self, obj):
        # FIX: Changed to obj.created_at
        return obj.created_at

    def location(self, obj):
        return reverse('video:video_detail', args=[obj.pk])