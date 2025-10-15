from django.shortcuts import render
from django.http import HttpResponse

def privacy_policy(request):
    return render(request, 'privacy.html')

def terms_conditions(request):
    return render(request, 'terms.html')

def about_us(request):
    return render(request, 'about.html')

def contact_us(request):
    return render(request, 'contact.html')

def sitemap_page(request):
    return render(request, 'sitemap.html')

def learnflow_overview(request):
    return render(request, 'learnflow_overview.html')  # ✅ matches your actual template filename