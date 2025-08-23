import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import Http404, HttpResponse

# Import models and forms from both aiapp and video apps
# Note: This is a common pattern for consolidating views in a smaller project.
from .models import Quiz, Question, Choice, StudentAnswer
from .forms import QuizForm # Import the QuizForm for proper form handling.
from video.models import Video
from video.forms import VideoForm

@login_required
def home(request):
    """
    Renders the home page of the application.
    This is a placeholder for a potential home view.
    """
    return render(request, 'aiapp/home.html')

@login_required
def quiz_list(request):
    """
    Renders a list of all quizzes for students to view.
    Quizzes are ordered by creation date in descending order.
    """
    quizzes = Quiz.objects.all().order_by('-created_at')
    return render(request, 'aiapp/quiz_list.html', {'quizzes': quizzes})

@login_required
def quiz_detail(request, quiz_id):
    """
    Displays the details of a specific quiz.
    Uses get_object_or_404 to handle cases where the quiz does not exist.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    return render(request, 'aiapp/quiz_detail.html', {'quiz': quiz})

@login_required
def quiz_attempt(request, quiz_id):
    """
    Handles the student's attempt at a quiz.

    This view fetches all questions for a given quiz. When the student submits
    the form, it processes their answers, calculates a score, and saves the
    results to the database. It expects the radio button values to be the
    primary keys (IDs) of the Choice objects.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.all()

    if request.method == 'POST':
        score = 0
        total_questions = questions.count()

        # Iterate through submitted answers
        for question in questions:
            # The name of the radio input is 'question_<question.id>'
            submitted_choice_id = request.POST.get(f'question_{question.id}')

            # Check if a choice was selected
            if submitted_choice_id:
                try:
                    # CRITICAL FIX: Convert the submitted ID to an integer
                    # This resolves the ValueError when the ID is a string like 'A'
                    selected_choice = get_object_or_404(Choice, pk=int(submitted_choice_id))
                    is_correct = selected_choice.is_correct
                    
                    if is_correct:
                        score += 1

                    # Save the student's answer
                    StudentAnswer.objects.create(
                        student=request.user,
                        question=question,
                        selected_choice=selected_choice,
                        is_correct=is_correct
                    )
                except (ValueError, Choice.DoesNotExist):
                    # Handle cases where the submitted ID is not a number (ValueError)
                    # or the choice does not exist in the database.
                    messages.error(request, 'An invalid choice was submitted.')
                    # Continue to process other questions if possible
                    continue
        
        # Store the results in the session and redirect to the results page
        request.session['quiz_score'] = score
        request.session['quiz_total_questions'] = total_questions
        # FIX: Changed the namespace from 'quizzes' to 'aiapp'
        return redirect('aiapp:quiz_results', quiz_id=quiz.id)

    # For a GET request, render the quiz attempt page
    return render(request, 'aiapp/quiz_attempt.html', {'quiz': quiz, 'questions': questions})

@login_required
def quiz_results(request, quiz_id):
    """
    Displays the results of a quiz attempt.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    # Retrieve score and total questions from the session
    score = request.session.pop('quiz_score', None)
    total_questions = request.session.pop('quiz_total_questions', None)
    
    # If session data is missing, redirect to quiz detail page
    if score is None or total_questions is None:
        messages.warning(request, "Quiz results not found. Please attempt the quiz again.")
        # FIX: Changed the namespace from 'quizzes' to 'aiapp'
        return redirect('aiapp:quiz_detail', quiz_id=quiz.id)
    
    return render(request, 'aiapp/quiz_results.html', {
        'quiz': quiz,
        'score': score,
        'total_questions': total_questions
    })

@login_required
def create_quiz(request):
    """
    Handles the creation of a new quiz and its questions.
    
    This function now correctly processes the JSON data sent from the
    dynamic create_quiz.html template, ensuring the quiz object is fully
    created before questions are added and redirecting to the quiz list.
    """
    if request.method == 'POST':
        quiz_form = QuizForm(request.POST)
        
        # Check if the quiz form data is valid.
        if quiz_form.is_valid():
            # Create a new quiz instance but don't save it to the database yet.
            # We need to set the teacher first.
            quiz = quiz_form.save(commit=False)
            quiz.teacher = request.user
            
            # Now, save the quiz to the database. This will generate a primary key (id).
            quiz.save()

            # The data for questions and choices is passed in the request.POST
            # as a JSON string from the JavaScript in the new template.
            questions_data = request.POST.get('questions_data')
            if questions_data:
                try:
                    questions_list = json.loads(questions_data)
                    for q_data in questions_list:
                        # Create and save each question, linking it to the newly created quiz.
                        question = Question.objects.create(
                            quiz=quiz,
                            text=q_data['text']
                        )
                        # Create and save each choice for the current question.
                        for c_data in q_data['choices']:
                            Choice.objects.create(
                                question=question,
                                text=c_data['text'],
                                is_correct=c_data['isCorrect']
                            )
                except json.JSONDecodeError:
                    # Handle the case where the JSON data is invalid.
                    messages.error(request, "Invalid question data format.")
                    # FIX: Changed the namespace from 'quizzes' to 'aiapp'
                    return redirect('aiapp:create_quiz')

            # Display a success message and redirect.
            messages.success(request, f'"{quiz.title}" has been created successfully!')
            # FIX: Changed the namespace from 'quizzes' to 'aiapp'
            return redirect('aiapp:quiz_list')
    else:
        quiz_form = QuizForm()
        
    return render(request, 'aiapp/create_quiz.html', {'quiz_form': quiz_form})

@login_required
def teacher_quiz_dashboard(request):
    """
    Displays a dashboard of quizzes created by the current user.
    """
    user_quizzes = Quiz.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'aiapp/teacher_quiz_dashboard.html', {'user_quizzes': user_quizzes})

@login_required
def edit_quiz(request, quiz_id):
    """
    Allows a teacher to edit an existing quiz.
    
    This view uses a GET request to display the form with existing data and
    a POST request to process the updated form data.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    # Check if the current user is the teacher of this quiz.
    if quiz.teacher != request.user:
        raise Http404

    if request.method == 'POST':
        quiz_form = QuizForm(request.POST, instance=quiz)
        if quiz_form.is_valid():
            quiz = quiz_form.save()
            
            # Update questions and choices based on submitted JSON data.
            questions_data = request.POST.get('questions_data')
            if questions_data:
                try:
                    questions_list = json.loads(questions_data)
                    
                    # Delete existing questions and choices to avoid duplicates.
                    # This is a simple but effective way to handle updates for a dynamic form.
                    quiz.questions.all().delete()
                    
                    for q_data in questions_list:
                        question = Question.objects.create(
                            quiz=quiz,
                            text=q_data['text']
                        )
                        for c_data in q_data['choices']:
                            Choice.objects.create(
                                question=question,
                                text=c_data['text'],
                                is_correct=c_data['isCorrect']
                            )
                except json.JSONDecodeError:
                    messages.error(request, "Invalid question data format.")
                    # FIX: Changed the namespace from 'quizzes' to 'aiapp'
                    return redirect('aiapp:edit_quiz', quiz_id=quiz.id)
            
            messages.success(request, f'"{quiz.title}" has been updated successfully!')
            # FIX: Changed the namespace from 'quizzes' to 'aiapp'
            return redirect('aiapp:teacher_quiz_dashboard')
    else:
        quiz_form = QuizForm(instance=quiz)
    
    return render(request, 'aiapp/edit_quiz.html', {'quiz_form': quiz_form, 'quiz': quiz})

@login_required
def delete_quiz(request, quiz_id):
    """
    Allows a teacher to delete a quiz.
    
    This view confirms the deletion via a POST request.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    # Check if the current user is the teacher of this quiz.
    if quiz.teacher != request.user:
        raise Http404
        
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, f'"{quiz.title}" has been deleted successfully!')
        # FIX: Changed the namespace from 'quizzes' to 'aiapp'
        return redirect('aiapp:teacher_quiz_dashboard')

    return render(request, 'aiapp/delete_quiz_confirm.html', {'quiz': quiz})

@login_required
def user_profile(request, user_id):
    """
    Displays the user profile page.
    """
    user_to_display = get_object_or_404(User, pk=user_id)
    # The template was previously named 'user_profile.html' but the file is 'profile_detail.html'.
    # This change corrects the template name to match the file.
    return render(request, 'aiapp/profile_detail.html', {'profile_user': user_to_display})

# Video-related views from the video app
@login_required
def video_list(request):
    """
    Renders a list of all available videos.
    """
    videos = Video.objects.all().order_by('-created_at')
    return render(request, 'video/video_list.html', {'videos': videos})

@login_required
def video_detail(request, video_id):
    """
    Renders the detail page for a single video.
    """
    video = get_object_or_404(Video, pk=video_id)
    return render(request, 'video/video_detail.html', {'video': video})

@login_required
def create_video(request):
    """
    Allows a teacher to upload a new video.
    """
    if request.method == 'POST':
        form = VideoForm(request.POST)
        if form.is_valid():
            video = form.save(commit=False)
            video.teacher = request.user
            video.save()
            # This is where the ManyToMany relationship is saved.
            # It must be done after the video object has been saved to the database.
            form.save_m2m()
            messages.success(request, f'"{video.title}" has been uploaded successfully!')
            return redirect('video:teacher_dashboard')
    else:
        form = VideoForm()
    return render(request, 'video/video_upload.html', {'form': form})

@login_required
def teacher_dashboard(request):
    """
    Displays a dashboard of videos uploaded by the current user.
    """
    user_videos = Video.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'video/teacher_dashboard.html', {'user_videos': user_videos})

@login_required
def edit_video(request, video_id):
    """
    Allows a teacher to edit an existing video.
    """
    video = get_object_or_404(Video, pk=video_id)
    
    if video.teacher != request.user:
        raise Http404
        
    if request.method == 'POST':
        form = VideoForm(request.POST, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{video.title}" has been updated successfully!')
            return redirect('video:teacher_dashboard')
    else:
        form = VideoForm(instance=video)

    return render(request, 'video/video_edit.html', {'form': form, 'video': video})

@login_required
def delete_video(request, video_id):
    """
    Allows a teacher to delete a video.
    """
    video = get_object_or_404(Video, pk=video_id)
    
    if video.teacher != request.user:
        raise Http404
        
    if request.method == 'POST':
        video.delete()
        messages.success(request, f'"{video.title}" has been deleted successfully!')
        return redirect('video:teacher_dashboard')

    return render(request, 'video/video_delete_confirm.html', {'video': video})
