from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.utils import timezone

# FIX: Changed from a relative import ('from .models import Quiz') 
# to the correct absolute import, assuming Quiz lives in the 'aiapp'.
from aiapp.models import Quiz 
from book.models import Book # Assuming Book is in the 'book' app
from video.models import Video # Assuming Video is in the 'video' app

# --- 1. Static Pages Sitemap ---
class StaticSitemap(Sitemap):
    """Sitemap for fixed, unchanging pages."""
    priority = 1.0
    changefreq = 'weekly'

    def items(self):
        # List the view names for all important static pages
        return ['aiapp:home', 'aiapp:quiz_list', 'video:video_list', 'book:book_list'] 

    def location(self, item):
        return reverse(item)
    
    def lastmod(self, item):
        # Static pages can use the current date or a hardcoded date
        return timezone.now()

# --- 2. Dynamic Content Sitemaps ---

class QuizSitemap(Sitemap):
    """Sitemap for all Quiz objects."""
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        # Filter for published or active quizzes if necessary
        return Quiz.objects.all().order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at 

    def location(self, obj):
        # Assumes your URL pattern is something like path('quiz/<int:quiz_id>/', views.quiz_detail, name='quiz_detail') 
        # inside the 'aiapp' namespace.
        return reverse('aiapp:quiz_detail', args=[obj.pk])

class BookSitemap(Sitemap):
    """Sitemap for all Book objects."""
    changefreq = "monthly"
    priority = 0.9

    def items(self):
        return Book.objects.all().order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at 

    def location(self, obj):
        # Assumes your URL pattern is inside the 'book' namespace.
        return reverse('book:book_detail', args=[obj.pk])

class VideoSitemap(Sitemap):
    """Sitemap for all Video objects."""
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return Video.objects.all().order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        # Assumes your URL pattern is inside the 'video' namespace.
        return reverse('video:video_detail', args=[obj.pk])