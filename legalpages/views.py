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
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

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
    return render(request, 'learnflow_overview.html', {}) 

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
    
    # Process lines for markdown structure
    for line in lines:
        line = line.strip()
        
        # Heading 1
        if line.startswith('## '):
            if in_list:
                story.append(ListFlowable(list_items, bulletType='bullet', start='bulletchar', bulletColor=colors.black, leftIndent=0.3*inch))
                list_items = []
                in_list = False
            story.append(Paragraph(line[3:], styles['Heading1']))
        # List item
        elif line.startswith('* ') or line.startswith('- '):
            list_items.append(ListItem(Paragraph(line[2:], styles['Normal'])))
            in_list = True
        else:
            if in_list:
                story.append(ListFlowable(list_items, bulletType='bullet', start='bulletchar', bulletColor=colors.black, leftIndent=0.3*inch))
                list_items = []
                in_list = False
            if line:
                story.append(Paragraph(line, styles['Normal']))

    # Finalize list if one was active
    if in_list:
        story.append(ListFlowable(list_items, bulletType='bullet', start='bulletchar', bulletColor=colors.black, leftIndent=0.3*inch))

    # Fallback for empty story (shouldn't happen with valid markdown)
    if not story and markdown_text:
        story.append(Paragraph(markdown_text, styles['Normal']))
    
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
    
    # Custom Styles
    styles.add(ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=24, alignment=1, spaceAfter=20, textColor=colors.HexColor('#00DDEB')))
    styles.add(ParagraphStyle(name='Heading1', fontName='Helvetica-Bold', fontSize=14, spaceBefore=15, spaceAfter=8, textColor=colors.HexColor('#3b82f6')))
    styles.add(ParagraphStyle(name='Normal', fontName='Helvetica', fontSize=10, spaceAfter=8))
    styles.add(ParagraphStyle(name='Question', fontName='Helvetica-Bold', fontSize=10, spaceAfter=4, textColor=colors.black))
    styles.add(ParagraphStyle(name='AnswerCorrect', fontName='Helvetica', fontSize=10, spaceBefore=2, spaceAfter=10, textColor=colors.HexColor('#10B981')))
    styles.add(ParagraphStyle(name='AnswerIncorrect', fontName='Helvetica', fontSize=10, spaceBefore=2, spaceAfter=10, textColor=colors.HexColor('#EF4444')))
    styles.add(ParagraphStyle(name='Metadata', fontName='Helvetica-Oblique', fontSize=8, spaceAfter=10, alignment=1))
    
    story = []

    # Report Title
    story.append(Paragraph("Nakintu AI - Video Analysis Report", styles['TitleStyle']))
    story.append(Paragraph(f"Analysis for: {title}", styles['Metadata']))
    story.append(Spacer(1, 0.2 * inch))

    # Summary Section
    story.append(Paragraph("--- 1. SUMMARY ---", styles['Heading1']))
    story.extend(markdown_to_story(summary, styles))
    story.append(Spacer(1, 0.1 * inch))

    # Quiz Section
    story.append(Paragraph("--- 2. QUIZ RESULTS ---", styles['Heading1']))
    if quiz_data and isinstance(quiz_data, list):
        for i, question_data in enumerate(quiz_data, 1):
            question = question_data.get('question', 'N/A')
            selected_answer = question_data.get('selected_answer', 'Not Answered')
            correct_answer = question_data.get('correct_answer', 'N/A')
            is_correct = question_data.get('is_correct', False)

            story.append(Paragraph(f"Q{i}: {question}", styles['Question']))
            
            # Display Selected Answer
            selected_style = styles['AnswerCorrect'] if is_correct else styles['AnswerIncorrect']
            selected_label = "✅ Your Answer (Correct)" if is_correct else "❌ Your Answer (Incorrect)"
            story.append(Paragraph(f"{selected_label}: {selected_answer}", selected_style))
            
            # Display Correct Answer if incorrect
            if not is_correct:
                story.append(Paragraph(f"Correct Answer: {correct_answer}", styles['AnswerCorrect']))
            
            story.append(Spacer(1, 0.1 * inch))
    else:
        story.append(Paragraph("Quiz results were not available or the quiz was not taken.", styles['Normal']))
    
    # Action Plan Section
    story.append(Paragraph("--- 3. ACTION PLAN ---", styles['Heading1']))
    story.extend(markdown_to_story(action_plan, styles))

    try:
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()
        return pdf_content, None
    except Exception as e:
        logging.error(f"Error building PDF: {e}")
        return None, f"Failed to generate PDF report: {e}"


# --- API/AJAX Views ---

@csrf_exempt
@require_http_methods(["POST"])
def analyze_video_api(request):
    """
    API endpoint to fetch a transcript and send it to the Gemini API for analysis.
    """
    try:
        data = json.loads(request.body)
        url = data.get('url')
        video_title = data.get('title', 'YouTube Video')
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON format in request body."}, status=400)
    
    if not url:
        return JsonResponse({"success": False, "error": "URL parameter is missing."}, status=400)
    
    # Extract video ID
    try:
        # Check for standard URL
        parsed_url = urlparse(url)
        if parsed_url.hostname in ['youtu.be', 'www.youtu.be']:
            video_id = parsed_url.path.lstrip('/')
        else:
            # Check for watch URL
            query = parse_qs(parsed_url.query)
            video_id = query.get('v', [None])[0]
        
        if not video_id:
            raise ValueError("ID extraction failed.")
        
    except Exception:
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
        return JsonResponse({"success": False, "error": f"AI Generation Error: {error}"}, status=500)

    # 4. Parse and Return Result
    try:
        # Clean the string, sometimes models add extra characters like ```json...```
        json_result_str = json_result_str.strip().lstrip('```json').rstrip('```')
        result_data = json.loads(json_result_str)
        
        # Add the video ID and title to the response
        result_data['video_id'] = video_id
        result_data['video_title'] = video_title
        
        return JsonResponse({"success": True, "data": result_data})

    except json.JSONDecodeError as e:
        logging.error(f"JSON Decoding Error after AI call: {e}")
        return JsonResponse({"success": False, "error": "AI response was not valid JSON."}, status=500)
    except Exception as e:
        logging.exception(f"CRITICAL UNHANDLED ERROR in analyze_video_api: {e}")
        return JsonResponse({"success": False, "error": "A critical server error occurred during analysis."}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def submit_quiz_api(request):
    """
    API endpoint to check user's quiz answers against the correct answers provided by the client.
    Note: In a production app, the correct answers should be stored server-side, not sent by the client.
    """
    try:
        data = json.loads(request.body)
        submitted_quiz = data.get('quiz', []) # Quiz structure from client
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format for quiz submission."}, status=400)
    
    graded_results = []
    total_questions = len(submitted_quiz)
    correct_count = 0

    # The client sends the entire quiz structure including the correct_answer.
    # We trust this structure for the grading logic here.
    for q in submitted_quiz:
        is_correct = q.get('selected_answer') == q.get('correct_answer')
        if is_correct:
            correct_count += 1
        
        # Prepare the result dictionary
        graded_results.append({
            'question': q.get('question'),
            'options': q.get('options'),
            'correct_answer': q.get('correct_answer'),
            'selected_answer': q.get('selected_answer'),
            'is_correct': is_correct
        })

    score = f"{correct_count}/{total_questions}"

    return JsonResponse({
        "success": True, 
        "graded_quiz": graded_results, 
        "score": score
    })

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
    sanitized_title = sanitize_filename(title)
    response['Content-Disposition'] = f'attachment; filename="{sanitized_title}.pdf"'
    
    return response