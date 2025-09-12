from django.db import models
from django.contrib.auth import get_user_model

# Use get_user_model() to reference the active user model
User = get_user_model()

class Quiz(models.Model):
    upload_code = models.CharField(max_length=10, blank=True, null=True, help_text="Admin-provided code to authorize uploads.")
    """Represents a quiz created by a teacher."""
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quizzes',
        help_text="The user who created this quiz.",
        db_index=True
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Quizzes"
        ordering = ['-created_at']

    def __str__(self):
        return self.title

class Question(models.Model):
    """A single question within a quiz."""
    QUESTION_TYPES = (
        ('MC', 'Multiple Choice'),
        ('SA', 'Single Answer'),
    )

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='questions',
        help_text="The quiz this question belongs to.",
        db_index=True
    )
    text = models.CharField(max_length=500)
    question_type = models.CharField(
        max_length=2,
        choices=QUESTION_TYPES,
        default='MC'
    )
    correct_answer_text = models.TextField(
        blank=True,
        null=True,
        help_text="The correct answer text for single-answer questions."
    )

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return self.text[:50]

class Choice(models.Model):
    """Represents a single answer choice for a question."""
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='choices',
        help_text="The question this choice belongs to.",
        db_index=True
    )
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ['text']

    def __str__(self):
        return self.text

class Attempt(models.Model):
    """Represents a single attempt by a user on a specific quiz."""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='quiz_attempts',
        db_index=True
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name='attempts',
        db_index=True
    )
    score = models.IntegerField(default=0)
    total_questions = models.IntegerField(default=0)
    submission_date = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'quiz']),
        ]

    def __str__(self):
        return f"{self.user.username}'s attempt on {self.quiz.title}"

class StudentAnswer(models.Model):
    """Records a student's answer to a specific question within an attempt."""
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='answers',
        db_index=True
    )
    attempt = models.ForeignKey(
        Attempt,
        on_delete=models.CASCADE,
        related_name='student_answers',
        help_text="The specific quiz attempt this answer belongs to.",
        null=True,
        blank=True,
        db_index=True
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name='student_answers',
        db_index=True
    )
    selected_choice = models.ForeignKey(
        Choice,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="The selected choice for a multiple-choice question.",
        db_index=True
    )
    text_answer = models.TextField(
        blank=True,
        null=True,
        help_text="The text entered by the student for a single-answer question."
    )
    is_correct = models.BooleanField()
    timestamp = models.DateTimeField(auto_now_add=True, null=True, db_index=True)

    class Meta:
        verbose_name_plural = "Student Answers"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['attempt', 'question']),
            models.Index(fields=['student', 'question']),
        ]

    def __str__(self):
        return f'{self.student.username} answered {self.question.text[:20]}...'