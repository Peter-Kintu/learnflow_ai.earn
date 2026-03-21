from django.shortcuts import render
from .models import StudentFee, PoultryRecord
from django.db.models import Sum

def dashboard_view(request):
    # Summary data for the home page
    total_fees_collected = StudentFee.objects.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    total_farm_sales = PoultryRecord.objects.aggregate(Sum('total_sales_revenue'))['total_sales_revenue__sum'] or 0
    
    context = {
        'total_fees': total_fees_collected,
        'total_sales': total_farm_sales,
    }
    return render(request, 'dashboard.html', context)

def fees_list(request):
    students = StudentFee.objects.all()
    return render(request, 'fees_list.html', {'students': students})

def farm_list(request):
    batches = PoultryRecord.objects.all()
    return render(request, 'farm_list.html', {'batches': batches})