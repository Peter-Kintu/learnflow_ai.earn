from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import StudentFee, PoultryRecord, SchoolExpense

@staff_member_required
def dashboard_view(request):
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
    if request.method == "POST" and 'save_record' in request.POST:
        StudentFee.objects.create(
            student_name=request.POST.get('student_name'),
            total_fees_required=request.POST.get('total_fees_required'),
            amount_paid=request.POST.get('amount_paid', 0)
        )
        messages.success(request, "Student added successfully!")
        return redirect('school:fees_list')

    students = StudentFee.objects.all().order_by('-id')
    return render(request, 'school/fees_list.html', {'students': students})

@staff_member_required
def farm_list(request):
    if request.method == "POST" and 'save_record' in request.POST:
        PoultryRecord.objects.create(
            batch_name=request.POST.get('batch_name'),
            number_of_chickens=request.POST.get('number_of_chickens'),
            chick_purchase_cost=request.POST.get('chick_purchase_cost'),
            feed_cost=request.POST.get('feed_cost', 0),
            total_sales_revenue=request.POST.get('total_sales_revenue', 0)
        )
        messages.success(request, "Farm batch saved!")
        return redirect('school:farm_list')

    batches = PoultryRecord.objects.all().order_by('-id')
    return render(request, 'school/farm_list.html', {'batches': batches})

@staff_member_required
def expense_list(request):
    if request.method == "POST":
        SchoolExpense.objects.create(
            category=request.POST.get('category'),
            amount=request.POST.get('amount'),
            description=request.POST.get('description')
        )
        messages.success(request, "Expense logged successfully!")
        return redirect('school:expense_list')

    expenses = SchoolExpense.objects.all().order_by('-date_spent')
    return render(request, 'school/expense_list.html', {'expenses': expenses})

@staff_member_required
def delete_record(request, model_type, pk):
    if request.method == "POST":
        pin = request.POST.get('delete_password')
        
        if pin and len(pin) == 5 and pin.isdigit():
            if model_type == 'fee':
                record = get_object_or_404(StudentFee, pk=pk)
                record.delete()
                messages.success(request, "Fee record deleted.")
            elif model_type == 'farm':
                record = get_object_or_404(PoultryRecord, pk=pk)
                record.delete()
                messages.success(request, "Farm record deleted.")
        else:
            messages.error(request, "Invalid PIN. Please enter any 5-digit numeric code.")
            
    return redirect(request.META.get('HTTP_REFERER', 'school:dashboard'))