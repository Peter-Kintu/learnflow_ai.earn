# aiapp/admin.py

from django.contrib import admin
from .models import Quiz, Question, Choice, StudentAnswer

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Quiz model in the admin panel.
    """
    list_display = ('title', 'teacher', 'created_at', 'updated_at')
    search_fields = ('title', 'teacher__username', 'description')
    list_filter = ('teacher', 'created_at')

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Question model.
    """
    list_display = ('text', 'quiz', 'question_type', 'get_correct_answer_display')
    list_filter = ('quiz', 'question_type')
    search_fields = ('text', 'quiz__title')

    def get_correct_answer_display(self, obj):
        """
        Custom method to display the correct answer based on the question type.
        """
        if obj.question_type == 'MC':
            try:
                # Find the correct choice for a Multiple Choice question
                return obj.choices.get(is_correct=True).text
            except Choice.DoesNotExist:
                return "No correct choice found."
        elif obj.question_type == 'SA':
            # Display the correct answer text for a Single Answer question
            return obj.correct_answer_text
        return "N/A"

    get_correct_answer_display.short_description = 'Correct Answer'


@admin.register(Choice)
class ChoiceAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Choice model.
    """
    list_display = ('text', 'question', 'is_correct')
    list_filter = ('question', 'is_correct')
    search_fields = ('text', 'question__text')

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    """
    Customizes the display of the StudentAnswer model.
    """
    list_display = ('student', 'question', 'selected_choice', 'text_answer', 'is_correct', 'timestamp')
    list_filter = ('student', 'question', 'is_correct', 'timestamp')
    search_fields = ('student__username', 'question__text', 'selected_choice__text', 'text_answer')
    readonly_fields = ('student', 'question', 'selected_choice', 'text_answer', 'is_correct', 'timestamp')