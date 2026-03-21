from django.shortcuts import render
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from .models import StudentFee, PoultryRecord

@staff_member_required
def dashboard_view(request):
    """Financial overview for School Fees and Farm Revenue."""
    fees_data = StudentFee.objects.aggregate(total=Sum('amount_paid'))
    farm_data = PoultryRecord.objects.aggregate(total=Sum('total_sales_revenue'))
    
    total_fees = fees_data['total'] or 0
    total_sales = farm_data['total'] or 0
    
    context = {
        'total_fees': total_fees,
        'total_sales': total_sales,
        'grand_total': total_fees + total_sales,
    }
    return render(request, 'school/dashboard.html', context)

@staff_member_required
def fees_list(request):
    students = StudentFee.objects.all().order_by('-id')
    return render(request, 'school/fees_list.html', {'students': students})

@staff_member_required
def farm_list(request):
    batches = PoultryRecord.objects.all().order_by('-id')
    return render(request, 'school/farm_list.html', {'batches': batches})