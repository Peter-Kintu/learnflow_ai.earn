# aiapp/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import Http404

# Import models and forms from both aiapp and video apps
# Note: This is a common pattern for consolidating views in a smaller project.
from .models import Quiz, Question, Choice, StudentAnswer
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
                    selected_choice = Choice.objects.get(pk=submitted_choice_id)
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
                except Choice.DoesNotExist:
                    # Handle the case where the selected choice does not exist
                    # This might happen if the form data is tampered with
                    messages.error(request, 'An invalid choice was submitted.')
                    # Continue to process other questions if possible
                    continue
        
        # Store the results in the session and redirect to the results page
        request.session['quiz_score'] = score
        request.session['quiz_total_questions'] = total_questions
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
    FIXED: Added a validation check for the quiz title to prevent an IntegrityError.
    """
    if request.method == 'POST':
        # Get quiz title and description from the form
        quiz_title = request.POST.get('quiz_title')
        quiz_description = request.POST.get('quiz_description')

        # Critical: Add a validation check for the title before creating the object
        if not quiz_title:
            messages.error(request, "Quiz title is required. Please provide a title.")
            # Re-render the form with the POST data to preserve user's input
            return render(request, 'aiapp/create_quiz.html', {'request': request, **request.POST})

        # Create the new Quiz instance
        try:
            quiz = Quiz.objects.create(
                teacher=request.user,
                title=quiz_title,
                description=quiz_description
            )
        except Exception as e:
            messages.error(request, f"An unexpected error occurred while creating the quiz: {e}")
            return render(request, 'aiapp/create_quiz.html', {'request': request, **request.POST})

        # Process questions and choices from the dynamically generated form
        question_count = 1
        while True:
            question_text = request.POST.get(f'question_text_{question_count}')
            if not question_text:
                # Break the loop if there are no more questions
                break

            # Get the correct option letter
            correct_option_letter = request.POST.get(f'correct_option_{question_count}')

            # Create the Question instance
            question = Question.objects.create(
                quiz=quiz,
                text=question_text
            )

            # Create the choices and set the correct one based on the form data
            Choice.objects.create(
                question=question,
                text=request.POST.get(f'option_a_{question_count}'),
                is_correct=(correct_option_letter and correct_option_letter.upper() == 'A')
            )
            Choice.objects.create(
                question=question,
                text=request.POST.get(f'option_b_{question_count}'),
                is_correct=(correct_option_letter and correct_option_letter.upper() == 'B')
            )
            Choice.objects.create(
                question=question,
                text=request.POST.get(f'option_c_{question_count}'),
                is_correct=(correct_option_letter and correct_option_letter.upper() == 'C')
            )
            Choice.objects.create(
                question=question,
                text=request.POST.get(f'option_d_{question_count}'),
                is_correct=(correct_option_letter and correct_option_letter.upper() == 'D')
            )
            
            question_count += 1

        messages.success(request, f'"{quiz.title}" has been created successfully!')
        # Redirect to a success page or the dashboard after saving
        return redirect('aiapp:quiz_list') 
    
    # If the request is a GET, just render the template
    return render(request, 'aiapp/create_quiz.html')

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
