from django.db import models
from django.core.exceptions import ValidationError

class StudentFee(models.Model):
    student_name = models.CharField(max_length=150)
    total_fees_required = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['student_name']
        verbose_name = "Student Fee"
        verbose_name_plural = "Student Fees"

    @property
    def balance_remaining(self):
        """Calculates the reducing balance automatically."""
        return self.total_fees_required - self.amount_paid

    def clean(self):
        """Prevents input errors where paid amount exceeds the requirement."""
        if self.amount_paid > self.total_fees_required:
            raise ValidationError({
                'amount_paid': f"Amount paid (UGX {self.amount_paid:,}) cannot exceed the total fees required (UGX {self.total_fees_required:,})."
            })

    def save(self, *args, **kwargs):
        self.full_clean()  # Triggers the clean() validation before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_name} (Bal: {self.balance_remaining:,.0f})"


class SchoolExpense(models.Model):
    category = models.CharField(max_length=100, help_text="e.g. Electricity, Water, Stationery")
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_spent = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-date_spent']

    def __str__(self):
        return f"{self.category}: {self.amount}"


class PoultryRecord(models.Model):
    batch_name = models.CharField(max_length=100, help_text="e.g. Broilers March 2026")
    number_of_chickens = models.PositiveIntegerField()
    
    # Separated Costs
    chick_purchase_cost = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Cost of Birds"
    )
    feed_cost = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name="Cost of Food"
    )
    other_costs = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0, 
        help_text="Medicines, charcoal, etc."
    )
    
    total_sales_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_started = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-date_started']
        verbose_name = "Poultry Record"
        verbose_name_plural = "Poultry Records"

    @property
    def total_investment(self):
        """Sum of all costs involved in the batch."""
        return self.chick_purchase_cost + self.feed_cost + self.other_costs

    @property
    def profit_or_loss(self):
        """Net financial result."""
        return self.total_sales_revenue - self.total_investment

    def __str__(self):
        return f"{self.batch_name} ({self.number_of_chickens} birds)"