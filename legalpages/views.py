import os
import logging
import time
import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlparse, parse_qs
from io import BytesIO 

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled 
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript, 
    VideoUnavailable, 
    NoTranscriptFound 
)

import google.genai as genai
from google.genai.errors import APIError
from google.genai import types 
from google.genai.types import HarmCategory, HarmBlockThreshold

# ----------------------------------------------------------------------
# FOR TESTING ONLY: Hardcoded Gemini API Key
# ----------------------------------------------------------------------
GEMINI_API_KEY = 'AIzaSyAPPxFduurg61JsZTq5w9GI9HQPKHWheKo'

# Imports for PDF Generation
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, ListFlowable, ListItem
    from reportlab.lib.units import inch
    PDF_ENABLED = True
except ImportError:
    logging.warning("ReportLab not installed. PDF generation will be mocked.")
    PDF_ENABLED = False

# --- AI Schema Definition ---

ANALYSIS_SCHEMA = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "summary": types.Schema(
            type=types.Type.STRING,
            description="A detailed, comprehensive summary of the video content in markdown format."
        ),
        "quiz": types.Schema(
            type=types.Type.ARRAY,
            description="A list of 3 multiple-choice questions based on the video content.",
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "question": types.Schema(type=types.Type.STRING),
                    "options": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                    "correct_answer": types.Schema(type=types.Type.STRING, description="The correct option from the list of options.")
                },
                required=["question", "options", "correct_answer"]
            )
        ),
        "action_plan": types.Schema(
            type=types.Type.STRING,
            description="A structured, actionable plan (3-5 steps) for the user to implement the knowledge gained, presented in markdown format."
        ),
    },
    required=["summary", "quiz", "action_plan"]
)


# --- Static Page Views (Kept for completeness) ---

def privacy_policy(request):
    return render(request, 'legalpages/privacy.html', {})

def terms_conditions(request):
    return render(request, 'legalpages/terms.html', {})

def about_us(request):
    return render(request, 'legalpages/about.html', {})

def contact_us(request):
    return render(request, 'legalpages/contact.html', {})

def sitemap_page(request):
    return render(request, 'legalpages/sitemap.html', {})

def learnflow_overview(request):
    return render(request, 'learnflow/overview.html', {}) 

def learnflow_video_analysis(request):
    return render(request, 'learnflow.html', {}) 

def video_analysis_view(request, video_id):
    context = {
        'video_id': video_id,
        'initial_url': f'https://www.youtube.com/watch?v={video_id}'
    }
    return render(request, 'learnflow.html', context)


# --- Utility Functions ---

def get_transcript_from_youtube(video_id):
    """
    Fetches the transcript for a given YouTube video ID, handling errors gracefully.
    Returns (transcript_text, error_message).
    """
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, 
            languages=['en', 'a.en', 'es', 'a.es', 'de', 'a.de', 'fr', 'a.fr']
        )
        transcript_text = ' '.join([item['text'] for item in transcript_list])
        return transcript_text, None
    except NoTranscriptFound:
        return None, "No suitable transcript found for this video. Try another language or video."
    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video."
    except VideoUnavailable:
        return None, "Video is unavailable or has been deleted."
    except CouldNotRetrieveTranscript as e:
        return None, f"Could not retrieve transcript: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred while fetching transcript for {video_id}: {e}")
        return None, "An unexpected error occurred during transcript retrieval."

def sanitize_filename(title, max_length=50):
    """Sanitizes a string to be safe for use as a filename."""
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_')
    return safe_title[:max_length] if safe_title else "report"


def call_gemini_api_with_retry(prompt, system_instruction=None, response_schema=None, max_retries=3):
    """
    Handles API calls to Gemini with built-in exponential backoff retry logic.
    Returns (result_text, error_message).
    """
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    generation_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json" if response_schema else "text/plain",
        response_schema=response_schema
    )

    safety_settings = [
        types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
        types.SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
        types.SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
        types.SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
    ]

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=generation_config,
                safety_settings=safety_settings
            )
            
            if not response.candidates or not response.text:
                return None, "AI response blocked due to safety settings or empty response."
                
            return response.text, None

        except APIError as e:
            error_message = f"Gemini API Error (Attempt {attempt+1}/{max_retries}): {e}"
            logging.warning(error_message)
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                time.sleep(sleep_time)
                continue
            return None, f"Final Gemini API failure: {error_message}"
        except Exception as e:
            error_message = f"An unexpected error occurred during API call: {e}"
            logging.error(error_message)
            return None, error_message
    
    return None, "Exceeded maximum retry attempts for Gemini API call."

# Helper function to convert markdown lists (which are often used by the AI) to ReportLab story elements
def markdown_to_story(markdown_text, styles):
    story = []
    lines = markdown_text.split('\n')
    
    list_items = []
    in_list = False
    
    for line in lines:
        if line.strip().startswith('* ') or line.strip().startswith('- '):
            list_items.append(line.strip()[2:].strip())
            in_list = True
        else:
            if in_list and list_items:
                # End of list, flush the list flowable
                flowable_list = ListFlowable(
                    [ListItem(Paragraph(item, styles['Normal']), bulletText='•') for item in list_items],
                    bulletType='bullet',
                    start='bullet',
                    indent=0.3 * inch,
                    leftIndent=0.3 * inch
                )
                story.append(flowable_list)
                list_items = []
                in_list = False
            
            if line.strip():
                # Treat other lines as normal paragraphs
                story.append(Paragraph(line.strip(), styles['Normal']))

    # Flush the final list if the text ended with one
    if in_list and list_items:
        flowable_list = ListFlowable(
            [ListItem(Paragraph(item, styles['Normal']), bulletText='•') for item in list_items],
            bulletType='bullet',
            start='bullet',
            indent=0.3 * inch,
            leftIndent=0.3 * inch
        )
        story.append(flowable_list)
        
    return story

def generate_pdf_report(title, summary, quiz_data, action_plan):
    """
    Generates a PDF report using ReportLab.
    Returns (pdf_content_bytes, error_message).
    """
    if not PDF_ENABLED:
        return None, "PDF generation library (ReportLab) is not installed."
        
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=inch/2, 
        leftMargin=inch/2, 
        topMargin=inch/2, 
        bottomMargin=inch/2
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=24, alignment=1, spaceAfter=20, textColor=colors.HexColor('#00DDEB')))
    styles.add(ParagraphStyle(name='Heading1', fontName='Helvetica-Bold', fontSize=14, spaceBefore=15, spaceAfter=8, textColor=colors.HexColor('#3b82f6')))
    styles.add(ParagraphStyle(name='Normal', fontName='Helvetica', fontSize=10, spaceAfter=8))
    styles.add(ParagraphStyle(name='Question', fontName='Helvetica-Bold', fontSize=10, spaceAfter=4, textColor=colors.black))
    styles.add(ParagraphStyle(name='AnswerCorrect', fontName='Helvetica', fontSize=10, spaceBefore=2, spaceAfter=10, textColor=colors.HexColor('#10B981')))
    styles.add(ParagraphStyle(name='AnswerIncorrect', fontName='Helvetica', fontSize=10, spaceBefore=2, spaceAfter=10, textColor=colors.HexColor('#EF4444')))
    styles.add(ParagraphStyle(name='Metadata', fontName='Helvetica-Oblique', fontSize=8, spaceAfter=10, alignment=1))

    story = []

    # Report Title
    story.append(Paragraph("LearnFlow AI - Video Analysis Report", styles['TitleStyle']))
    story.append(Paragraph(f"Analysis for: {title}", styles['Metadata']))
    story.append(Spacer(1, 0.2 * inch))

    # Summary Section
    story.append(Paragraph("--- 1. SUMMARY ---", styles['Heading1']))
    story.extend(markdown_to_story(summary, styles))
    story.append(Spacer(1, 0.2 * inch))

    # Quiz Results Section
    story.append(Paragraph("--- 2. QUIZ RESULTS ---", styles['Heading1']))
    quiz_results_found = False
    
    if quiz_data and quiz_data.get('questions'):
        quiz_results_found = True
        score = quiz_data.get('score', 0)
        total = quiz_data.get('total_questions', 0)
        story.append(Paragraph(f"Final Score: <font size='12' color='#00DDEB'><b>{score} / {total}</b></font>", styles['Normal']))

        for i, q in enumerate(quiz_data['questions']):
            is_correct = q.get('is_correct', False)
            style = styles['AnswerCorrect'] if is_correct else styles['AnswerIncorrect']
            
            story.append(Paragraph(f"Question {i+1}: {q['question']}", styles['Question']))
            story.append(Paragraph(f"Your Answer: <font color='{style.textColor.hexa() if is_correct else styles['AnswerIncorrect'].textColor.hexa()}'><b>{q['user_answer']} ({'CORRECT' if is_correct else 'INCORRECT'})</b></font>", styles['Normal']))
            
            if not is_correct:
                 story.append(Paragraph(f"Correct Answer: <font color='{styles['AnswerCorrect'].textColor.hexa()}'><b>{q['correct_answer']}</b></font>", styles['Normal']))
            
            story.append(Spacer(1, 0.1 * inch))

    if not quiz_results_found:
        story.append(Paragraph("Quiz results were not provided or the quiz was not scored.", styles['Normal']))

    story.append(Spacer(1, 0.2 * inch))

    # Action Plan Section
    story.append(Paragraph("--- 3. ACTION PLAN ---", styles['Heading1']))
    story.extend(markdown_to_story(action_plan, styles))

    try:
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()
        return pdf_content, None
    except Exception as e:
        logging.error(f"ReportLab PDF generation failed: {e}")
        return None, "Failed to build PDF document. Check server logs."


# --- API Views ---

@csrf_exempt
@require_http_methods(["POST"])
def analyze_video_api(request):
    """
    API endpoint to fetch transcript, analyze with Gemini, and return the structured data.
    CRITICAL: Contains top-level error handling to prevent silent 500 errors.
    """
    try:
        data = json.loads(request.body)
        video_url = data.get('video_url')
        video_title = data.get('video_title', 'Unknown Video')

        if not video_url:
            return JsonResponse({"success": False, "error": "Video URL is required."}, status=400)

        # Robust YouTube ID extraction
        video_id = urlparse(video_url).query
        if 'v=' in video_id:
            video_id = parse_qs(video_id).get('v', [''])[0]
        else:
            path_parts = urlparse(video_url).path.split('/')
            video_id = path_parts[-1] if path_parts[-1] else path_parts[-2]

        if not video_id or len(video_id) != 11:
             return JsonResponse({"success": False, "error": "Invalid YouTube video ID extracted."}, status=400)

        # 1. Fetch Transcript
        transcript_text, error = get_transcript_from_youtube(video_id)

        if error:
            # Transcript errors are expected (e.g., disabled captions)
            return JsonResponse({"success": False, "error": f"Transcript Error: {error}"}, status=404)

        # 2. Prepare AI Prompt
        system_instruction = (
            "You are an expert educational assistant specializing in summarizing video transcripts, "
            "creating challenging multiple-choice quizzes (3 questions, 4 options each), and generating a 3-5 step action plan. "
            "Output MUST be in the requested JSON format."
        )
        prompt = (
            f"Video Title: '{video_title}'.\n\n"
            f"Transcript:\n---\n{transcript_text}\n---\n\n"
            "Based on the transcript, generate a comprehensive summary, a 3-question quiz with 4 options each, and a 3-5 step action plan. Ensure the output strictly follows the provided JSON schema."
        )

        # 3. Call Gemini API
        json_result_str, error = call_gemini_api_with_retry(
            prompt=prompt,
            system_instruction=system_instruction,
            response_schema=ANALYSIS_SCHEMA
        )

        if error:
            return JsonResponse({"success": False, "error": f"AI Generation Failed: {error}"}, status=500)

        # 4. Parse and Return JSON
        try:
            analysis_result = json.loads(json_result_str)
        except json.JSONDecodeError:
            logging.error(f"AI returned non-JSON content: {json_result_str[:500]}...")
            return JsonResponse({"success": False, "error": "AI returned invalid JSON format. Try again."}, status=500)

        # Add the title back for the frontend
        analysis_result['video_title'] = video_title

        return JsonResponse({"success": True, **analysis_result}, status=200)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON request body."}, status=400)
    except Exception as e:
        # CATCH-ALL: This is the critical block that prevents silent 500 errors.
        logging.exception(f"CRITICAL UNHANDLED ERROR in analyze_video_api: {e}")
        return JsonResponse({"success": False, "error": "A critical server error occurred. Check backend logs for a Python traceback."}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def submit_quiz_api(request):
    """
    API endpoint to submit quiz results and get AI grading (simple echo for now).
    """
    try:
        data = json.loads(request.body)
        quiz_data = data.get('quiz_data', [])
        
        # Simple grading logic (in a real app, this would use AI for more complex grading/feedback)
        total_questions = len(quiz_data)
        correct_count = 0
        
        graded_questions = []
        for q in quiz_data:
            is_correct = (q['user_answer'] == q['correct_answer'])
            if is_correct:
                correct_count += 1
            graded_questions.append({
                'question': q['question'],
                'user_answer': q['user_answer'],
                'correct_answer': q['correct_answer'],
                'is_correct': is_correct
            })

        grading_result = {
            "score": correct_count,
            "total_questions": total_questions,
            "questions": graded_questions
        }

        return JsonResponse({"success": True, "grading_data": grading_result})

    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format for quiz submission."}, status=400)
    except Exception as e:
        logging.exception(f"CRITICAL UNHANDLED ERROR in submit_quiz_api: {e}")
        return JsonResponse({"success": False, "error": "A critical server error occurred during quiz submission."}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def export_content_api(request):
    """
    API endpoint to generate and return the PDF report.
    """
    try:
        data = json.loads(request.body)
        title = data.get('video_title', 'Video Analysis Report')
        summary = data.get('summary', 'No summary provided.')
        quiz_data = data.get('quiz_data', {}) # Contains graded results
        action_plan = data.get('action_plan', 'No action plan provided.')
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
    
    pdf_content, error_message = generate_pdf_report(title, summary, quiz_data, action_plan)
    
    if error_message:
        return JsonResponse({"error": error_message}, status=500)
    
    # Return the PDF file as a Django HttpResponse
    response = HttpResponse(pdf_content, content_type='application/pdf')
    # Use the video title for the filename, sanitized
    filename = sanitize_filename(title)
    response['Content-Disposition'] = f'attachment; filename="{filename}_report.pdf"'
    
    return response