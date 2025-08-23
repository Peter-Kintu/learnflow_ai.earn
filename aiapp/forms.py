# aiapp/forms.py

from django import forms

class QuizForm(forms.Form):
    """
    A Django form for creating a quiz.

    This form is designed to handle user input for generating a quiz.
    The `quiz_topic` field will be a text area where the user can enter
    the subject they want a quiz on.
    """
    quiz_topic = forms.CharField(
        label='Enter the topic for your quiz',
        widget=forms.Textarea(attrs={'rows': 4, 'cols': 40}),
    )

    # You can add more fields here if needed, for example:
    # num_questions = forms.IntegerField(
    #     label='Number of questions',
    #     min_value=1,
    #     max_value=10,
    #     initial=5
    # )

