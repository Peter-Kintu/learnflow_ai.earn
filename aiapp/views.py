import io
import json
from .tasks import ask_learnflow_ai
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.template.loader import get_template
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from docx import Document

# Import the necessary libraries for PDF generation
from xhtml2pdf import pisa

# Import models and forms from both aiapp and video apps
from .models import Quiz, Question, Choice, StudentAnswer, Attempt
from .forms import QuizForm
from video.models import Video
from video.forms import VideoForm
from book.models import Book


from django.contrib.auth.decorators import login_required
from django.shortcuts import render


import json
from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt

# NOTE: For this to work with your AI models, you'll need to import
# and use them here. This is a placeholder for the actual AI logic.
 # adjust if Quiz is in another app

@login_required
def home(request):
    """
    Renders the AI-powered home page with personalized context.
    """
    return render(request, 'aiapp/home.html', {
        "user": request.user,
        "username": request.user.get_full_name() or request.user.username,
        "ai_context": "LearnFlow AI is here to empower educators and learners across Africa. Ask anything!"
    })
# @csrf_exempt
# def chat_api(request):
#     """
#     Handles POST requests for the chat API.
#     Receives a user query and returns a placeholder AI response.
#     """
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             query = data.get('query', '')
            
#             # --- Placeholder for AI model logic ---
#             # Replace this with your actual AI model's code to generate a response.
#             ai_response = f"I received your message: '{query}'. This is a placeholder response."
#             # -------------------------------------

#             return JsonResponse({'answer': ai_response})
#         except json.JSONDecodeError:
#             return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    
#     return JsonResponse({'error': 'Invalid request method'}, status=405)


# @csrf_exempt
# def feedback_api(request):
#     """
#     Handles POST requests for the feedback API.
#     Saves feedback to a log file or a database.
#     """
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             feedback = data.get('feedback', '')
            
#             # --- Placeholder for feedback storage ---
#             # You can save this to a file, database, or send it to a different service.
#             # For now, let's just log it to the console.
#             print(f"Received user feedback: '{feedback}'")
#             # ---------------------------------------

#             return JsonResponse({'message': 'Feedback received successfully'})
#         except json.JSONDecodeError:
#             return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
    
#     return JsonResponse({'error': 'Invalid request method'}, status=405)

def ask_ai_view(request):
    query = request.POST.get("query")
    task = ask_learnflow_ai.delay(query)
    return JsonResponse({"task_id": task.id})

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
            print("Rendered HTML:", html)
    except Exception as e:
        print("Exception during PDF generation:", str(e))
    return None



@login_required
def quiz_list(request):
    """
    Renders a list of all quizzes for students to view.
    """
    quizzes = Quiz.objects.order_by('-created_at')
    return render(request, 'aiapp/quiz_list.html', {'quizzes': quizzes})

@login_required
def quiz_detail(request, quiz_id):
    """
    Displays the details of a specific quiz.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    return render(request, 'aiapp/quiz_detail.html', {'quiz': quiz})

@login_required
@transaction.atomic
def quiz_attempt(request, quiz_id):
    """
    Handles the student's attempt at a quiz.
    """
    quiz = get_object_or_404(Quiz, id=quiz_id)
    questions = quiz.questions.all()

    if request.method == 'POST':
        score = 0
        total_questions = questions.count()

        new_attempt = Attempt.objects.create(
            user=request.user,
            quiz=quiz,
            score=0,
            total_questions=total_questions
        )

        for question in questions:
            is_correct = False
            selected_choice = None
            submitted_answer_text = None

            if question.question_type == 'MC':
                submitted_choice_id = request.POST.get(f'question_{question.id}', None)
                if submitted_choice_id:
                    try:
                        selected_choice = Choice.objects.get(pk=int(submitted_choice_id))
                        is_correct = selected_choice.is_correct
                    except (ValueError, ObjectDoesNotExist):
                        is_correct = False
            
            elif question.question_type == 'SA':
                submitted_answer_text = request.POST.get(f'question_{question.id}', '')
                if submitted_answer_text.strip():
                    is_correct = (submitted_answer_text.strip().lower() == question.correct_answer_text.strip().lower())
                else:
                    is_correct = False
            
            StudentAnswer.objects.create(
                student=request.user,
                question=question,
                selected_choice=selected_choice,
                text_answer=submitted_answer_text,
                is_correct=is_correct,
                attempt=new_attempt
            )
            
            if is_correct:
                score += 1
        
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
        passed = attempt.score >= (attempt.total_questions * 0.5)

        # Calculate the percentage and the SVG stroke-dashoffset here
        if attempt.total_questions > 0:
            score_percentage = attempt.score / attempt.total_questions
            score_offset = 339.29 * (1 - score_percentage)
        else:
            score_percentage = 0
            score_offset = 339.29 # Full circle offset if no questions

        return render(request, 'aiapp/quiz_results.html', {
            'quiz': attempt.quiz,
            'score': attempt.score,
            'total_questions': attempt.total_questions,
            'attempt_id': attempt.id,
            'passed': passed,
            'score_percentage': score_percentage,
            'score_offset': score_offset,
        })
    except Exception as e:
        print("Error rendering quiz results:", str(e))
        return HttpResponse("Error displaying results", status=500)

@login_required
def quiz_review(request, attempt_id):
    """
    Displays a detailed review of a specific quiz attempt.
    """
    attempt = get_object_or_404(Attempt, pk=attempt_id, user=request.user)
    student_answers = StudentAnswer.objects.filter(attempt=attempt).select_related('question', 'selected_choice')
    
    questions_and_answers = []
    for q in attempt.quiz.questions.all():
        try:
            student_answer = student_answers.get(question=q)
        except ObjectDoesNotExist:
            student_answer = None
        
        questions_and_answers.append({
            'question': q,
            'student_answer': student_answer,
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
            quiz.upload_code = quiz_form.cleaned_data.get('upload_code')
            quiz.save()
            
            questions_data = request.POST.get('questions_data')
            if questions_data:
                try:
                    questions_list = json.loads(questions_data)
                    for q_data in questions_list:
                        question_text = q_data.get('text')
                        if not question_text:
                            continue

                        question_type = q_data.get('question_type', 'MC')
                        
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
                    raise
        else:
            messages.error(request, "Please correct the form errors below.")
            print("Form errors:", quiz_form.errors)
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
                    
                    existing_question_ids = set(quiz.questions.values_list('id', flat=True))
                    questions_to_keep = set()

                    for q_data in questions_list:
                        question_id = q_data.get('id')
                        question_text = q_data.get('text')
                        if not question_text:
                            continue
                        
                        question_type = q_data.get('question_type', 'MC')
                        
                        if question_id and str(question_id).isdigit():
                            question_instance = Question.objects.get(pk=question_id, quiz=quiz)
                            question_instance.text = question_text
                            question_instance.question_type = question_type
                            
                            questions_to_keep.add(int(question_id))
                        else:
                            question_instance = Question.objects.create(
                                quiz=quiz,
                                text=question_text,
                                question_type=question_type,
                            )
                        
                        if question_type == 'MC':
                            question_instance.choice_set.all().delete()
                            choices_data = q_data.get('choices', [])
                            for c_data in choices_data:
                                if c_data.get('text'):
                                    Choice.objects.create(
                                        question=question_instance,
                                        text=c_data['text'],
                                        is_correct=c_data.get('isCorrect', False)
                                    )
                            question_instance.correct_answer_text = None
                            question_instance.save()
                        elif question_type == 'SA':
                            correct_answer_text = q_data.get('correct_answer_text')
                            if correct_answer_text:
                                question_instance.correct_answer_text = correct_answer_text
                            else:
                                question_instance.correct_answer_text = ""
                            question_instance.save()
                            question_instance.choice_set.all().delete()

                    questions_to_delete_ids = existing_question_ids - questions_to_keep
                    Question.objects.filter(id__in=questions_to_delete_ids, quiz=quiz).delete()
                                        
                    messages.success(request, f'"{quiz.title}" has been updated successfully!')
                    return redirect('aiapp:teacher_quiz_dashboard')

                except (json.JSONDecodeError, KeyError, ObjectDoesNotExist) as e:
                    print(f"JSON processing error: {e}")
                    messages.error(request, "There was an error processing the quiz questions. Please check the data and try again.")
                    raise
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
def quiz_report_pdf_for_quiz(request, quiz_id):
    """Generates a PDF report for a specific quiz, including all student attempts."""
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    if request.user != quiz.teacher:
        raise Http404

    attempts = Attempt.objects.filter(quiz=quiz)
    enriched_attempts = []

    for a in attempts:
        percentage = round((a.score / a.total_questions) * 100) if a.total_questions else 0
        incorrect = a.total_questions - a.score
        enriched_attempts.append({
            'user': a.user,
            'score': a.score,
            'total_questions': a.total_questions,
            'percentage': percentage,
            'incorrect_answers': incorrect,
        })

    context = {
        'quiz': quiz,
        'attempts': enriched_attempts,
        'report_date': timezone.now(),
        'request_user': request.user,
    }

    try:
        pdf = render_to_pdf('aiapp/quiz_report_pdf.html', context)
        if pdf:
            filename = f"{quiz.title.replace(' ', '_')}_report.pdf"
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f"attachment; filename='{filename}'"
            return response
    except Exception as e:
        print("PDF generation error:", str(e))

    return HttpResponse("Error generating PDF", status=500)

def build_quiz_attempt_context(attempt, request_user):
    student_answers = StudentAnswer.objects.filter(attempt=attempt).select_related('question', 'selected_choice')
    score = attempt.score
    total_questions = attempt.total_questions
    percentage = round((score / total_questions) * 100) if total_questions else 0
    incorrect_answers = total_questions - score

    enriched_answers = []
    for ans in student_answers:
        correct_choice = ans.question.choices.filter(is_correct=True).first()
        user_answer = ans.selected_choice.text if ans.selected_choice else ans.text_answer
        correct_answer = correct_choice.text if correct_choice else "N/A"
        is_correct = user_answer == correct_answer
        feedback = "✅ Well done!" if is_correct else f"❌ Almost there — the correct answer was '{correct_answer}'. Keep going!"

        enriched_answers.append({
            'question_text': ans.question.text,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'feedback': feedback,
        })

    return {
        'quiz': attempt.quiz,
        'attempt': attempt,
        'report_date': timezone.now(),
        'request_user': request_user,
        'score': score,
        'total_questions': total_questions,
        'percentage': percentage,
        'incorrect_answers': incorrect_answers,
        'user': attempt.user,
        'today': timezone.now(),
        'answers': enriched_answers,
    }    

@login_required
def quiz_report_pdf_for_attempt(request, attempt_id):
    """Generates a PDF report for a specific quiz attempt, including correct answers and feedback."""
    attempt = get_object_or_404(Attempt, pk=attempt_id)
    if request.user != attempt.user and request.user != attempt.quiz.teacher:
        raise Http404

    student_answers = StudentAnswer.objects.filter(attempt=attempt).select_related('question', 'selected_choice')
    score = attempt.score
    total_questions = attempt.total_questions
    percentage = round((score / total_questions) * 100) if total_questions else 0
    incorrect_answers = total_questions - score

    enriched_answers = []
    for ans in student_answers:
        correct_choice = ans.question.choices.filter(is_correct=True).first()
        user_answer = ans.selected_choice.text if ans.selected_choice else ans.text_answer
        correct_answer = correct_choice.text if correct_choice else "N/A"
        is_correct = user_answer == correct_answer

        feedback = (
            "✅ Well done!" if is_correct else
            f"❌ Almost there — the correct answer was '{correct_answer}'. Keep going!"
        )

        enriched_answers.append({
            'question_text': ans.question.text,
            'user_answer': user_answer,
            'correct_answer': correct_answer,
            'is_correct': is_correct,
            'feedback': feedback,
        })

    context = {
        'quiz': attempt.quiz,
        'attempt': attempt,
        'report_date': timezone.now(),
        'request_user': request.user,
        'score': score,
        'total_questions': total_questions,
        'percentage': percentage,
        'incorrect_answers': incorrect_answers,
        'user': attempt.user,
        'today': timezone.now(),
        'answers': enriched_answers,
    }

    try:
        pdf = render_to_pdf('aiapp/quiz_report_pdf.html', context)
        if pdf:
            filename = f"{attempt.quiz.title.replace(' ', '_')}_report_attempt_{attempt.id}.pdf"
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f"attachment; filename='{filename}'"
            return response
    except Exception as e:
        print("PDF generation error:", str(e))

    return HttpResponse("Error generating PDF", status=500)



@login_required
def quiz_report_word_for_attempt(request, attempt_id):
    attempt = get_object_or_404(Attempt, pk=attempt_id)
    if request.user != attempt.user and request.user != attempt.quiz.teacher:
        raise Http404

    context = build_quiz_attempt_context(attempt, request.user)
    doc = Document()
    doc.add_heading(f'Quiz Report - {context["quiz"].title}', 0)
    doc.add_paragraph(f'Generated for {context["user"].username} on {context["today"].strftime("%B %d, %Y")}')

    doc.add_heading('Summary', level=1)
    doc.add_paragraph(f'Score: {context["score"]} / {context["total_questions"]}')
    doc.add_paragraph(f'Correct: {context["score"]}')
    doc.add_paragraph(f'Incorrect: {context["incorrect_answers"]}')
    doc.add_paragraph(f'Percentage: {context["percentage"]}%')

    doc.add_heading('Questions and Answers', level=1)
    for i, ans in enumerate(context['answers'], start=1):
        doc.add_paragraph(f'Question {i}: {ans["question_text"]}', style='List Number')
        doc.add_paragraph(f'Your Answer: {ans["user_answer"]}')
        doc.add_paragraph(f'Correct Answer: {ans["correct_answer"]}')
        doc.add_paragraph(f'Feedback: {ans["feedback"]}')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    filename = f"{context['quiz'].title.replace(' ', '_')}_attempt_{attempt.id}.docx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    doc.save(response)
    return response

def why_learnflow_ai(request):
    return render(request, 'aiapp/why_learnflow_ai.html')


def sitemap_view(request):
    base_url = "https://learnflow-ai-0fdz.onrender.com"
    urls = [
        f"{base_url}/",
        f"{base_url}/aiapp/",
        f"{base_url}/video/",
        f"{base_url}/book/",
    ]

    try:
        urls += [f"{base_url}/quiz/{getattr(q, 'slug', q.pk)}/" for q in Quiz.objects.all()]
    except Exception:
        urls.append(f"{base_url}/quiz/")

    try:
        urls += [f"{base_url}/books/{getattr(b, 'slug', b.pk)}/" for b in Book.objects.all()]
    except Exception:
        urls.append(f"{base_url}/books/")

    try:
        urls += [f"{base_url}/video/{getattr(v, 'slug', v.pk)}/" for v in Video.objects.all()]
    except Exception:
        urls.append(f"{base_url}/video/")

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    for url in urls:
        xml += f'  <url><loc>{url}</loc></url>\n'
    xml += '</urlset>'

    return HttpResponse(xml, content_type='application/xml')

@login_required
def retake_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    return redirect('aiapp:quiz_attempt', quiz_id=quiz.id)

