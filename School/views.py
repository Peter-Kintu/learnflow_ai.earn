from django.shortcuts import render
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from .models import StudentFee, PoultryRecord

@staff_member_required
def dashboard_view(request):
    """
    Financial overview for School Fees and Farm Revenue.
    Restricted to staff members only.
    """
    # Use aggregation to get totals; default to 0 if None
    fees_data = StudentFee.objects.aggregate(total=Sum('amount_paid'))
    farm_data = PoultryRecord.objects.aggregate(total=Sum('total_sales_revenue'))
    
    total_fees = fees_data['total'] or 0
    total_sales = farm_data['total'] or 0
    
    context = {
        'total_fees': total_fees,
        'total_sales': total_sales,
        'grand_total': total_fees + total_sales,
    }
    # Path namespaced to 'school/' folder for better organization
    return render(request, 'school/dashboard.html', context)

@staff_member_required
def fees_list(request):
    """List of all student fee records."""
    students = StudentFee.objects.all().order_by('-id')
    return render(request, 'school/fees_list.html', {'students': students})

@staff_member_required
def farm_list(request):
    """List of all poultry/farm batch records."""
    batches = PoultryRecord.objects.all().order_by('-id')
    return render(request, 'school/farm_list.html', {'batches': batches})