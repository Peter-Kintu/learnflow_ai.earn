from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.utils import timezone
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from .models import StudentFee, PoultryRecord, SchoolExpense, PiggeryRecord, LocalChickenRecord

@staff_member_required
def dashboard_view(request):
    # We use the current year for the dashboard totals
    current_year = timezone.now().year
    
    # 1. School Fees Total for the CURRENT YEAR
    fees_yearly = StudentFee.objects.filter(
        academic_year=current_year
    ).aggregate(total=Sum('amount_paid'))['total'] or 0
    
    # 2. Expenses Total for the CURRENT YEAR
    expenses_yearly = SchoolExpense.objects.filter(
        academic_year=current_year
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    # 3. Farm Revenue (Cumulative across all time)
    poultry_total = PoultryRecord.objects.aggregate(total=Sum('total_sales_revenue'))['total'] or 0
    piggery_total = PiggeryRecord.objects.aggregate(total=Sum('total_sales_revenue'))['total'] or 0
    local_chicken_total = LocalChickenRecord.objects.aggregate(total=Sum('total_sales_revenue'))['total'] or 0
    total_sales = poultry_total + piggery_total + local_chicken_total
    
    context = {
        'current_year': current_year,
        'total_fees': fees_yearly, # Now reflects current year only
        'total_sales': total_sales,
        'expenses_yearly': expenses_yearly,
        'grand_total': fees_yearly + total_sales,
        'net_position': (fees_yearly + total_sales) - expenses_yearly,
    }
    return render(request, 'school/dashboard.html', context)

@staff_member_required
def fees_list(request):
    # Get term and year from URL parameters, or use current defaults
    selected_term = request.GET.get('term', 'Term 1')
    selected_year = int(request.GET.get('year', timezone.now().year))

    if request.method == "POST" and 'save_record' in request.POST:
        StudentFee.objects.create(
            student_name=request.POST.get('student_name'),
            total_fees_required=request.POST.get('total_fees_required'),
            amount_paid=request.POST.get('amount_paid', 0),
            # Save specific term and year from the form
            term=request.POST.get('term', selected_term),
            academic_year=request.POST.get('academic_year', selected_year)
        )
        messages.success(request, f"Student added to {selected_term}!")
        return redirect(f'/fees/?term={selected_term}&year={selected_year}')

    # Filter students by term and year
    students = StudentFee.objects.filter(
        term=selected_term, 
        academic_year=selected_year
    ).order_by('-id')
    
    # CALCULATE TOTAL MONEY COLLECTED FOR THIS TERM
    term_total = students.aggregate(total=Sum('amount_paid'))['total'] or 0

    return render(request, 'school/fees_list.html', {
        'students': students,
        'term_total': term_total,
        'selected_term': selected_term,
        'selected_year': selected_year
    })

@staff_member_required
def expense_list(request):
    selected_term = request.GET.get('term', 'Term 1')
    selected_year = int(request.GET.get('year', timezone.now().year))

    if request.method == "POST":
        SchoolExpense.objects.create(
            category=request.POST.get('category'),
            amount=request.POST.get('amount'),
            description=request.POST.get('description'),
            term=request.POST.get('term', selected_term),
            academic_year=request.POST.get('academic_year', selected_year)
        )
        messages.success(request, "Expense logged successfully!")
        return redirect(f'/expenses/?term={selected_term}&year={selected_year}')

    # Filter expenses by term and year
    expenses = SchoolExpense.objects.filter(
        term=selected_term, 
        academic_year=selected_year
    ).order_by('-date_spent')
    
    # CALCULATE TOTAL EXPENSES FOR THIS TERM
    term_expense_total = expenses.aggregate(total=Sum('amount'))['total'] or 0

    return render(request, 'school/expense_list.html', {
        'expenses': expenses,
        'term_expense_total': term_expense_total,
        'selected_term': selected_term,
        'selected_year': selected_year
    })

@staff_member_required
def farm_list(request):
    if request.method == "POST" and 'save_record' in request.POST:
        PoultryRecord.objects.create(
            batch_name=request.POST.get('batch_name'),
            number_of_chickens=request.POST.get('number_of_chickens'),
            chick_purchase_cost=request.POST.get('chick_purchase_cost'),
            feed_cost=request.POST.get('feed_cost', 0),
            other_costs=request.POST.get('other_costs', 0),
            total_sales_revenue=request.POST.get('total_sales_revenue', 0)
        )
        messages.success(request, "Poultry batch saved!")
        return redirect('school:farm_list')

    batches = PoultryRecord.objects.all().order_by('-id')
    return render(request, 'school/farm_list.html', {'batches': batches})

@staff_member_required
def piggery_list(request):
    if request.method == "POST" and 'save_record' in request.POST:
        PiggeryRecord.objects.create(
            batch_name=request.POST.get('batch_name'),
            number_of_pigs=request.POST.get('number_of_pigs'),
            piglet_purchase_cost=request.POST.get('purchase_cost'),
            feed_cost=request.POST.get('feed_cost', 0),
            treatment_cost=request.POST.get('treatment_cost', 0),
            total_sales_revenue=request.POST.get('total_sales_revenue', 0)
        )
        messages.success(request, "Piggery record saved!")
        return redirect('school:piggery_list')

    batches = PiggeryRecord.objects.all().order_by('-id')
    return render(request, 'school/pigery.html', {'batches': batches})

@staff_member_required
def local_chicken_list(request):
    if request.method == "POST" and 'save_record' in request.POST:
        LocalChickenRecord.objects.create(
            batch_name=request.POST.get('batch_name'),
            number_of_birds=request.POST.get('number_of_birds'),
            purchase_cost=request.POST.get('purchase_cost'),
            feed_cost=request.POST.get('feed_cost', 0),
            total_sales_revenue=request.POST.get('total_sales_revenue', 0)
        )
        messages.success(request, "Local chicken record saved!")
        return redirect('school:local_chicken_list')

    batches = LocalChickenRecord.objects.all().order_by('-id')
    return render(request, 'school/localchicken.html', {'batches': batches})

@staff_member_required
def delete_record(request, model_type, pk):
    if request.method == "POST":
        pin = request.POST.get('delete_password')
        
        if pin and len(pin) == 5 and pin.isdigit():
            if model_type == 'fee':
                get_object_or_404(StudentFee, pk=pk).delete()
                messages.success(request, "Fee record deleted.")
            elif model_type == 'farm':
                get_object_or_404(PoultryRecord, pk=pk).delete()
                messages.success(request, "Poultry record deleted.")
            elif model_type == 'piggery':
                get_object_or_404(PiggeryRecord, pk=pk).delete()
                messages.success(request, "Piggery record deleted.")
            elif model_type == 'local_chicken':
                get_object_or_404(LocalChickenRecord, pk=pk).delete()
                messages.success(request, "Local chicken record deleted.")
        else:
            messages.error(request, "Invalid PIN. Please enter your 5-digit code.")
            
    return redirect(request.META.get('HTTP_REFERER', 'school:dashboard'))