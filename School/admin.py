from django.contrib import admin
from django.utils.html import format_html
from .models import StudentFee, PoultryRecord, SchoolExpense, PiggeryRecord, LocalChickenRecord

@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    # Display columns including the new Term and Year fields
    list_display = ('student_name', 'term', 'academic_year', 'total_fees_required', 'amount_paid', 'colored_balance')
    
    # Enable filtering by Term and Year in the sidebar
    list_filter = ('term', 'academic_year', 'total_fees_required')
    
    # Search by student name
    search_fields = ('student_name',)

    def colored_balance(self, obj):
        bal = obj.balance_remaining
        if bal > 0:
            return format_html('<b style="color: red;">Debt: {:,}</b>', bal)
        elif bal < 0:
            return format_html('<b style="color: blue;">Overpaid: {:,}</b>', abs(bal))
        return format_html('<b style="color: green;">Cleared</b>')
    
    colored_balance.short_description = "Balance Status"

@admin.register(PoultryRecord)
class PoultryAdmin(admin.ModelAdmin):
    list_display = ('batch_name', 'number_of_chickens', 'total_investment', 'total_sales_revenue', 'profit_status', 'date_started')
    list_filter = ('date_started',)
    search_fields = ('batch_name',)
    
    def profit_status(self, obj):
        res = obj.profit_or_loss
        color = "green" if res >= 0 else "red"
        label = "Profit" if res >= 0 else "Loss"
        return format_html('<b style="color: {};">{}: {:,}</b>', color, label, abs(res))

@admin.register(PiggeryRecord)
class PiggeryAdmin(admin.ModelAdmin):
    list_display = ('batch_name', 'number_of_pigs', 'total_investment', 'total_sales_revenue', 'profit_status', 'date_started')
    list_filter = ('date_started',)
    search_fields = ('batch_name',)
    
    def profit_status(self, obj):
        res = obj.profit_or_loss
        color = "green" if res >= 0 else "red"
        label = "Profit" if res >= 0 else "Loss"
        return format_html('<b style="color: {};">{}: {:,}</b>', color, label, abs(res))

@admin.register(LocalChickenRecord)
class LocalChickenAdmin(admin.ModelAdmin):
    list_display = ('batch_name', 'number_of_birds', 'total_investment', 'total_sales_revenue', 'profit_status', 'date_started')
    list_filter = ('date_started',)
    search_fields = ('batch_name',)
    
    def profit_status(self, obj):
        res = obj.profit_or_loss
        color = "green" if res >= 0 else "red"
        label = "Profit" if res >= 0 else "Loss"
        return format_html('<b style="color: {};">{}: {:,}</b>', color, label, abs(res))

@admin.register(SchoolExpense)
class SchoolExpenseAdmin(admin.ModelAdmin):
    list_display = ('category', 'term', 'academic_year', 'amount', 'date_spent')
    # Filter expenses by Term and Year to match the new dashboard logic
    list_filter = ('term', 'academic_year', 'category', 'date_spent')
    search_fields = ('category', 'description')