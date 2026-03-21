from django.contrib import admin
from django.utils.html import format_html
from .models import StudentFee, PoultryRecord

@admin.register(StudentFee)
class StudentFeeAdmin(admin.ModelAdmin):
    # What shows up in the table view
    list_display = ('student_name', 'total_fees_required', 'amount_paid', 'colored_balance')
    
    # Search by name
    search_fields = ('student_name',)
    
    # Filter by fees (useful if different classes have different fee structures)
    list_filter = ('total_fees_required',)

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
    list_display = ('batch_name', 'number_of_chickens', 'total_investment', 'total_sales_revenue', 'profit_status')
    
    def profit_status(self, obj):
        res = obj.profit_or_loss
        color = "green" if res >= 0 else "red"
        label = "Profit" if res >= 0 else "Loss"
        return format_html('<b style="color: {};">{}: {:,}</b>', color, label, abs(res))