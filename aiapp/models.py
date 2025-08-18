# aiapp/models.py

from django.db import models
from django.contrib.auth.models import User
# The circular import was here. This import is not needed for the models in this file.
# from video.models import Video

class Quiz(models.Model):
    """
    Represents a quiz created by a teacher.
    """
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='quizzes')
    title = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

class Question(models.Model):
    """
    A single question within a quiz.
    """
    # Define choices for the question type
    QUESTION_TYPES = (
        ('MC', 'Multiple Choice'),
        ('SA', 'Single Answer'),
    )

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.CharField(max_length=500)
    question_type = models.CharField(
        max_length=2,
        choices=QUESTION_TYPES,
        default='MC'
    )
    # This field will be used for single-answer questions
    correct_answer_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.text[:50]

class Choice(models.Model):
    """
    Represents a single answer choice for a question.
    """
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class StudentAnswer(models.Model):
    """
    Records a student's answer to a specific question.
    """
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='student_answers')
    # Made selected_choice nullable to allow migration on existing data
    selected_choice = models.ForeignKey(Choice, on_delete=models.CASCADE, null=True, blank=True)
    # New field to store the text answer for single-answer questions
    text_answer = models.TextField(blank=True, null=True)
    is_correct = models.BooleanField()
    # Adding a timestamp field to track when the answer was submitted
    # Making it nullable to prevent errors on existing rows
    timestamp = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return f'{self.student.username} answered {self.question.text[:20]}'

