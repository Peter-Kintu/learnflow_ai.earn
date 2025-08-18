# aiapp/admin.py

from django.contrib import admin
from .models import Quiz, Question, Choice, StudentAnswer

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Quiz model in the admin panel.
    """
    list_display = ('title', 'teacher', 'created_at')
    search_fields = ('title', 'teacher__username')
    list_filter = ('teacher',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Question model.
    """
    list_display = ('text', 'quiz', 'get_correct_choice_text')
    list_filter = ('quiz',)

    def get_correct_choice_text(self, obj):
        """
        Custom method to display the correct choice text in the list view.
        """
        try:
            return obj.choices.get(is_correct=True).text
        except Choice.DoesNotExist:
            return "No correct choice"

    get_correct_choice_text.short_description = 'Correct Answer'


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Choice model.
    """
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('question',)

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    """
    Customizes the display of the StudentAnswer model.
    """
    # The 'timestamp' field does not exist on the StudentAnswer model.
    # We will remove it from the list_display tuple to fix the SystemCheckError.
    list_display = ('student', 'question', 'selected_choice', 'is_correct')
    list_filter = ('student', 'question', 'is_correct')
