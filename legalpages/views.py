from django.shortcuts import render
from django.http import HttpResponse

def privacy_policy(request):
    return render(request, 'legalpages/privacy.html')

def terms_conditions(request):
    return render(request, 'legalpages/terms.html')

def about_us(request):
    return render(request, 'legalpages/about.html')

def contact_us(request):
    return render(request, 'legalpages/contact.html')

def sitemap_page(request):
    return render(request, 'legalpages/sitemap.html')

def learnflow_overview(request):
    return render(request, 'legalpages/overview.html')