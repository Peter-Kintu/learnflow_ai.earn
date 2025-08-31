# aiapp/models.py

from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

# Use get_user_model() to reference the active user model
User = get_user_model()

class Quiz(models.Model):
    """
    Represents a quiz created by a teacher.
    """
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quizzes',
        help_text="The user who created this quiz."
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Quizzes"
        # Default ordering for quizzes in descending order of creation date
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class Question(models.Model):
    """
    A single question within a quiz.
    """
    QUESTION_TYPES = (
        ('MC', 'Multiple Choice'),
        ('SA', 'Single Answer'),
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        help_text="The quiz this question belongs to."
    )
    text = models.CharField(max_length=500)
    question_type = models.CharField(
        max_length=2,
        choices=QUESTION_TYPES,
        default='MC'
    )
    # This field will be used for single-answer questions
    correct_answer_text = models.TextField(blank=True, null=True, help_text="The correct answer text for single-answer questions.")

    class Meta:
        # Default ordering for questions within a quiz
        ordering = ['pk']

    def __str__(self):
        return self.text[:50]

class Choice(models.Model):
    """
    Represents a single answer choice for a question.
    """
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        help_text="The question this choice belongs to."
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        # Default ordering for choices within a question
        ordering = ['text']

    def __str__(self):
        return self.text

class StudentAnswer(models.Model):
    """
    Records a student's answer to a specific question.
    """
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='answers'
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='student_answers'
    )
    selected_choice = models.ForeignKey(
        Choice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The selected choice for a multiple-choice question."
    )
    # New field to store the text answer for single-answer questions
    text_answer = models.TextField(
        blank=True,
        null=True,
        help_text="The text entered by the student for a single-answer question."
    )
    is_correct = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        verbose_name_plural = "Student Answers"
        # Default ordering for student answers
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.student.username} answered {self.question.text[:20]}...'