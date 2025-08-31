import io
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.template.loader import get_template
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

# Import the necessary libraries for PDF generation
from xhtml2pdf import pisa

# Import models and forms from both aiapp and video apps
from .models import Quiz, Question, Choice, StudentAnswer, Attempt
from .forms import QuizForm
from video.models import Video
from video.forms import VideoForm

def render_to_pdf(template_src, context_dict={}):
    """
    Renders a Django template to a PDF file.
    """
    try:
        template = get_template(template_src)
        html = template.render(context_dict)
        result = io.BytesIO()
        pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
        if not pdf.err:
            return HttpResponse(result.getvalue(), content_type='application/pdf')
        else:
            print("PDF generation error:", pdf.err)
            print("Rendered HTML:", html)  # Optional: helps debug template issues
    except Exception as e:
        print("Exception during PDF generation:", str(e))
    return None

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
    quizzes = Quiz.objects.order_by('-created_at')
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
@transaction.atomic
def quiz_attempt(request, quiz_id):
    """
    Handles the student's attempt at a quiz.
    
    This view fetches all questions for a given quiz. When the student submits
    the form, it processes their answers, calculates a score, and saves the
    results to the database. It now handles both Multiple Choice (MC) and
    Single Answer (SA) question types.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.all()

    if request.method == 'POST':
        score = 0
        total_questions = questions.count()

        # Create a new Attempt object to store this session's results
        new_attempt = Attempt.objects.create(
            user=request.user,
            quiz=quiz,
            score=0,
            total_questions=total_questions
        )

        for question in questions:
            is_correct = False
            
            if question.question_type == 'MC':
                submitted_choice_id = request.POST.get(f'question_{question.id}')
                if submitted_choice_id:
                    try:
                        selected_choice = Choice.objects.get(pk=int(submitted_choice_id))
                        is_correct = selected_choice.is_correct
                        StudentAnswer.objects.create(
                            student=request.user,
                            question=question,
                            selected_choice=selected_choice,
                            is_correct=is_correct,
                            attempt=new_attempt
                        )
                    except (ValueError, ObjectDoesNotExist):
                        # Handle invalid or missing choices gracefully
                        pass
            
            elif question.question_type == 'SA':
                submitted_answer_text = request.POST.get(f'question_{question.id}')
                if submitted_answer_text:
                    # Compare the submitted text to the correct answer, case-insensitively and trimmed
                    is_correct = (submitted_answer_text.strip().lower() == question.correct_answer_text.strip().lower())
                    StudentAnswer.objects.create(
                        student=request.user,
                        question=question,
                        text_answer=submitted_answer_text,
                        is_correct=is_correct,
                        attempt=new_attempt
                    )
            
            if is_correct:
                score += 1
        
        # Update the score on the new Attempt object
        new_attempt.score = score
        new_attempt.save()

        return redirect('aiapp:quiz_results', attempt_id=new_attempt.id)

    return render(request, 'aiapp/quiz_attempt.html', {'quiz': quiz, 'questions': questions})

@login_required
def quiz_results(request, attempt_id):
    """
    Displays the results of a specific quiz attempt.
    """
    try:
        attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
        answers = StudentAnswer.objects.filter(attempt=attempt)

        detailed_answers = []
        for answer in answers:
            correct_answer_display = ""
            if answer.question.question_type == 'MC':
                # Safely get the correct option for multiple choice questions
                try:
                    correct_choice = answer.question.choice_set.get(is_correct=True)
                    correct_answer_display = correct_choice.text
                except (ObjectDoesNotExist, AttributeError):
                    correct_answer_display = "N/A"
            else: # SA questions
                correct_answer_display = answer.question.correct_answer_text

            detailed_answers.append({
                'question': answer.question,
                'user_answer': answer.text_answer if answer.text_answer else (answer.selected_choice.text if answer.selected_choice else "No Answer"),
                'is_correct': answer.is_correct,
                'correct_answer_display': correct_answer_display
            })

        # Calculate the 'passed' status in the view
        passed = attempt.score >= (attempt.total_questions / 2)

        context = {
            'quiz': attempt.quiz,
            'score': attempt.score,
            'total_questions': attempt.total_questions,
            'attempt_id': attempt.id,
            'passed': passed,
            'answers': detailed_answers,
        }
        return render(request, 'aiapp/quiz_results.html', context)
    except Exception as e:
        print(f"Error in quiz_results view: {str(e)}")
        return render(request, 'aiapp/error.html', {'message': 'Something went wrong displaying the results.'}, status=500)

@login_required
def quiz_review(request, attempt_id):
    """
    Displays a detailed review of a specific quiz attempt, showing correct and incorrect answers.
    """
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    student_answers = StudentAnswer.objects.filter(attempt=attempt).select_related('question', 'selected_choice')
    
    questions_and_answers = []
    for q in attempt.quiz.questions.all():
        try:
            student_answer = student_answers.get(question=q)
            questions_and_answers.append({
                'question': q,
                'student_answer': student_answer,
            })
        except ObjectDoesNotExist:
            # Handle un-answered questions
            questions_and_answers.append({
                'question': q,
                'student_answer': None,
            })

    context = {
        'attempt': attempt,
        'questions_and_answers': questions_and_answers
    }
    return render(request, 'aiapp/quiz_review.html', context)

@login_required
@transaction.atomic
def create_quiz(request):
    """
    Handles the creation of a new quiz and its questions.
    """
    if request.method == 'POST':
        quiz_form = QuizForm(request.POST)
        
        if quiz_form.is_valid():
            quiz = quiz_form.save(commit=False)
            quiz.teacher = request.user
            quiz.save()
            
            questions_data = request.POST.get('questions_data')
            if questions_data:
                try:
                    questions_list = json.loads(questions_data)
                    for q_data in questions_list:
                        question_text = q_data.get('text')
                        if not question_text:
                            continue

                        question_type = q_data.get('question_type', 'MC') # Default to MC if type is missing
                        
                        question_instance = Question.objects.create(
                            quiz=quiz,
                            text=question_text,
                            question_type=question_type,
                        )

                        if question_type == 'MC':
                            choices_data = q_data.get('choices', [])
                            for c_data in choices_data:
                                if c_data.get('text'):
                                    Choice.objects.create(
                                        question=question_instance,
                                        text=c_data['text'],
                                        is_correct=c_data.get('isCorrect', False)
                                    )
                        elif question_type == 'SA':
                            correct_answer_text = q_data.get('correct_answer_text')
                            if correct_answer_text:
                                question_instance.correct_answer_text = correct_answer_text
                                question_instance.save()

                    messages.success(request, f'"{quiz.title}" has been created successfully!')
                    return redirect('aiapp:teacher_quiz_dashboard')

                except (json.JSONDecodeError, KeyError) as e:
                    print(f"JSON processing error: {e}")
                    messages.error(request, "There was an error processing the quiz questions. Please check the data and try again.")
                    # Re-raise to trigger the atomic block's rollback
                    raise
        else:
            messages.error(request, "Please correct the form errors below.")
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
@transaction.atomic
def edit_quiz(request, quiz_id):
    """
    Allows a teacher to edit an existing quiz.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    if quiz.teacher != request.user:
        raise Http404

    if request.method == 'POST':
        quiz_form = QuizForm(request.POST, instance=quiz)
        if quiz_form.is_valid():
            quiz = quiz_form.save()
            
            questions_data = request.POST.get('questions_data')
            if questions_data:
                try:
                    questions_list = json.loads(questions_data)
                    
                    # Get existing question IDs to find which ones were deleted
                    existing_question_ids = set(quiz.questions.values_list('id', flat=True))
                    questions_to_keep = set()

                    for q_data in questions_list:
                        question_id = q_data.get('id')
                        question_text = q_data.get('text')
                        if not question_text:
                            continue
                        
                        question_type = q_data.get('question_type', 'MC')
                        
                        if question_id and str(question_id).isdigit():
                            # This is an existing question, update it
                            question_instance = Question.objects.get(pk=question_id, quiz=quiz)
                            question_instance.text = question_text
                            question_instance.question_type = question_type
                            
                            # Add its ID to the set of questions to keep
                            questions_to_keep.add(int(question_id))
                        else:
                            # This is a new question, create it
                            question_instance = Question.objects.create(
                                quiz=quiz,
                                text=question_text,
                                question_type=question_type,
                            )
                        
                        # Handle choices for MC and SA questions
                        if question_type == 'MC':
                            question_instance.choice_set.all().delete() # Clear existing choices
                            choices_data = q_data.get('choices', [])
                            for c_data in choices_data:
                                if c_data.get('text'):
                                    Choice.objects.create(
                                        question=question_instance,
                                        text=c_data['text'],
                                        is_correct=c_data.get('isCorrect', False)
                                    )
                            # Clear SA field to avoid conflicts
                            question_instance.correct_answer_text = None
                            question_instance.save()
                        elif question_type == 'SA':
                            # For SA, update the correct_answer_text directly on the question
                            correct_answer_text = q_data.get('correct_answer_text')
                            if correct_answer_text:
                                question_instance.correct_answer_text = correct_answer_text
                            else:
                                question_instance.correct_answer_text = ""
                            question_instance.save()
                            # Clear choices to avoid conflicts
                            question_instance.choice_set.all().delete()

                    # Delete questions that were removed from the form
                    questions_to_delete_ids = existing_question_ids - questions_to_keep
                    Question.objects.filter(id__in=questions_to_delete_ids, quiz=quiz).delete()
                            
                    messages.success(request, f'"{quiz.title}" has been updated successfully!')
                    return redirect('aiapp:teacher_quiz_dashboard')

                except (json.JSONDecodeError, KeyError, ObjectDoesNotExist) as e:
                    print(f"JSON processing error: {e}")
                    messages.error(request, "There was an error processing the quiz questions. Please check the data and try again.")
                    raise # Rollback the transaction
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        quiz_form = QuizForm(instance=quiz)
        
    return render(request, 'aiapp/edit_quiz.html', {'quiz_form': quiz_form, 'quiz': quiz})

@login_required
def delete_quiz(request, quiz_id):
    """
    Allows a teacher to delete a quiz.
    """
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    if quiz.teacher != request.user:
        raise Http404
        
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, f'"{quiz.title}" has been deleted successfully!')
        return redirect('aiapp:teacher_quiz_dashboard')

    return render(request, 'aiapp/delete_quiz_confirm.html', {'quiz': quiz})

@login_required
def user_profile(request, user_id):
    """
    Displays the user profile page.
    """
    user_to_display = get_object_or_404(User, pk=user_id)
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

@login_required
def quiz_report_pdf(request, attempt_id):
    """
    Generates a PDF report for a specific quiz attempt.
    """
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    student_answers = StudentAnswer.objects.filter(attempt=attempt)

    detailed_answers = []
    for answer in student_answers:
        correct_answer_display = ""
        if answer.question.question_type == 'MC':
            try:
                correct_choice = answer.question.choice_set.get(is_correct=True)
                correct_answer_display = correct_choice.text
            except (ObjectDoesNotExist, AttributeError):
                correct_answer_display = "N/A"
        else:
            correct_answer_display = answer.question.correct_answer_text

        detailed_answers.append({
            'question_text': answer.question.text,
            'user_answer': answer.text_answer if answer.text_answer else (answer.selected_choice.text if answer.selected_choice else "No Answer"),
            'is_correct': answer.is_correct,
            'correct_answer_display': correct_answer_display
        })
    
    context = {
        'quiz': attempt.quiz,
        'attempt': attempt,
        'student_answers': detailed_answers,
        'report_date': timezone.now(),
    }
    
    # Render the PDF
    pdf = render_to_pdf('aiapp/quiz_report_pdf.html', context)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"{attempt.quiz.title.replace(' ', '_')}_{attempt.id}_report.pdf"
        content = f"attachment; filename='{filename}'"
        response['Content-Disposition'] = content
        return response
    
    return HttpResponse("Error generating PDF", status=500)
