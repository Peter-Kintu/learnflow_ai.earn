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
        return self.total_fees_required - self.amount_paid

    def clean(self):
        if self.amount_paid > self.total_fees_required:
            raise ValidationError({
                'amount_paid': f"Amount paid (UGX {self.amount_paid:,}) cannot exceed required fees."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_name} (Bal: {self.balance_remaining:,.0f})"


class PoultryRecord(models.Model):
    batch_name = models.CharField(max_length=100, help_text="e.g. Broilers March 2026")
    number_of_chickens = models.PositiveIntegerField()
    chick_purchase_cost = models.DecimalField(max_digits=12, decimal_places=2)
    feed_cost = models.DecimalField(max_digits=12, decimal_places=2)
    other_costs = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_sales_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    date_started = models.DateField(auto_now_add=True)

    class Meta:
        ordering = ['-date_started']

    @property
    def total_investment(self):
        return self.chick_purchase_cost + self.feed_cost + self.other_costs

    @property
    def profit_or_loss(self):
        return self.total_sales_revenue - self.total_investment