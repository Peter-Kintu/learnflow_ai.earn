import os
import logging
import time
import json
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from urllib.parse import urlparse, parse_qs
from io import BytesIO 
from reportlab.lib.utils import ImageReader
from django.views.decorators.http import require_http_methods # New: Restrict to POST
from django.contrib.auth.decorators import login_required # New: Secure the API endpoints

# Imports for Transcript Fetching
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api._errors import CouldNotRetrieveTranscript, VideoUnavailable 

# Imports for Gemini AI
import google.genai as genai
from google.genai.errors import APIError
from google.genai import types 
from google.genai.types import HarmCategory, HarmBlockThreshold # For safety settings

# Imports for PDF Generation
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    PDF_ENABLED = True
except ImportError:
    logging.warning("ReportLab not installed. PDF generation will be mocked.")
    PDF_ENABLED = False


logger = logging.getLogger(__name__)

# --- Senior Dev Constants for Robustness ---
MAX_RETRIES = 3
TRANSCRIPT_FALLBACK_MARKER = "NO_TRANSCRIPT_AVAILABLE"
# Initialize Gemini Client
try:
    GEMINI_CLIENT = genai.Client()
except Exception as e:
    logger.error(f"Failed to initialize Gemini Client: {e}")
    GEMINI_CLIENT = None


def get_video_id(url):
    """Safely extracts the YouTube video ID from a URL."""
    try:
        if 'youtu.be' in url:
            return urlparse(url).path.strip('/')
        query = urlparse(url).query
        return parse_qs(query).get('v', [None])[0]
    except Exception:
        return None

def fetch_transcript_robust(video_id):
    """Fetches transcript with advanced error handling and language fallbacks."""
    if not video_id:
        return TRANSCRIPT_FALLBACK_MARKER, "Invalid video ID."

    try:
        # Tries to retrieve the English transcript first
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Prioritize English, then English auto-generated, then the first available
        transcript = transcript_list.find_transcript(['en'])
        if not transcript:
             transcript = transcript_list.find_transcript(['en'], exact_match=False)

        transcript_data = transcript.fetch()
        full_transcript = " ".join([item['text'] for item in transcript_data])
        
        return full_transcript, ""

    except (NoTranscriptFound, TranscriptsDisabled, CouldNotRetrieveTranscript) as e:
        error_message = f"Transcript error: {e.__class__.__name__}. The video may not have a transcript, or it is disabled."
        logger.warning(f"Failed to get transcript for {video_id}: {error_message}")
        return TRANSCRIPT_FALLBACK_MARKER, error_message
    
    except VideoUnavailable:
        error_message = "Video is unavailable or private."
        logger.error(f"Video unavailable: {video_id}")
        return TRANSCRIPT_FALLBACK_MARKER, error_message
        
    except Exception as e:
        error_message = f"An unexpected error occurred while fetching transcript: {e}"
        logger.exception(f"Unexpected error for {video_id}")
        return TRANSCRIPT_FALLBACK_MARKER, error_message

def generate_ai_content_robust(prompt):
    """Calls Gemini API with retries and structured safety settings."""
    if not GEMINI_CLIENT:
        return None, "Gemini client is not initialized. Check API Key configuration."

    model_name = 'gemini-2.5-flash'
    
    # Senior Dev: Set appropriate safety settings for educational content
    safety_config = types.SafetySetting(
        category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
        threshold=HarmBlockThreshold.BLOCK_NONE
    )
    
    for attempt in range(MAX_RETRIES):
        try:
            response = GEMINI_CLIENT.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    safety_settings=[safety_config]
                )
            )
            # Check for empty response and retry if necessary
            if response.text.strip():
                return response.text, ""
            
        except APIError as e:
            logger.warning(f"Gemini API Error (Attempt {attempt + 1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt) # Exponential backoff
                continue
            return None, f"Gemini API failed after {MAX_RETRIES} attempts. Details: {e}"
        except Exception as e:
            logger.exception(f"An unexpected error occurred during AI generation: {e}")
            return None, f"An unexpected server error occurred: {e}"
            
    return None, f"AI generation failed to return content after {MAX_RETRIES} attempts."

def create_video_analysis_pdf(video_title, summary, quiz_results, final_score, total_questions):
    """
    Generates a PDF report using ReportLab.
    """
    if not PDF_ENABLED:
        return None, "PDF generation library (ReportLab) is not installed on the server."

    buffer = BytesIO()
    # Senior Dev: Use A4 for better print compatibility
    doc = SimpleDocTemplate(buffer, pagesize=A4, title=f"LearnFlow AI Report: {video_title}")
    styles = getSampleStyleSheet()
    
    elements = []
    
    # Title
    elements.append(Paragraph(f"<b>LearnFlow AI Video Analysis Report</b>", styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Video Title
    elements.append(Paragraph(f"Video: <b>{video_title}</b>", styles['h2']))
    elements.append(Spacer(1, 12))

    # Summary Section
    elements.append(Paragraph("<u>Video Summary</u>", styles['h2']))
    # Use a basic style for long text
    summary_style = ParagraphStyle(name='BodyText', parent=styles['Normal'], leading=14)
    # The summary from AI is likely to have newlines, replace them with <br/> for ReportLab
    clean_summary = summary.replace('\n', '<br/>')
    elements.append(Paragraph(clean_summary, summary_style))
    elements.append(Spacer(1, 24))

    # Quiz Results Section
    elements.append(Paragraph("<u>Quiz Results</u>", styles['h2']))
    elements.append(Paragraph(f"Final Score: <b>{final_score} out of {total_questions}</b>", styles['Normal']))
    elements.append(Spacer(1, 12))

    # Quiz Details Table
    data = [['Question', 'Your Answer', 'Correct Answer', 'Result']]
    for item in quiz_results:
        question = Paragraph(item.get('question', 'N/A'), styles['Normal'])
        user_answer = Paragraph(item.get('user_answer', 'N/A'), styles['Normal'])
        correct_answer = Paragraph(item.get('correct_answer', 'N/A'), styles['Normal'])
        result = "✅ Correct" if item.get('is_correct') else "❌ Incorrect"
        data.append([question, user_answer, correct_answer, result])

    # Senior Dev: Use a Table for structured data
    table = Table(data, colWidths=[200, 100, 100, 60])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 24))
    
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf, ""

# =========================================================================
# --- API Endpoints (REMOVED @csrf_exempt and ADDED @require_http_methods) ---
# =========================================================================

@require_http_methods(["POST"])
@login_required # Assuming user authentication is desirable for AI endpoints
def analyze_video_api(request):
    """
    Analyzes a video transcript to generate a summary and quiz questions.
    """
    try:
        # Safely parse JSON request body
        data = json.loads(request.body.decode('utf-8'))
        video_url = data.get('videoLink')
        video_title = data.get('videoTitle', 'Untitled Video')
        
        if not video_url:
            return JsonResponse({"status": "error", "message": "Video URL is required."}, status=400)
        
        video_id = get_video_id(video_url)
        if not video_id:
            return JsonResponse({"status": "error", "message": "Could not extract a valid YouTube video ID from the URL."}, status=400)

        # 1. Fetch Transcript (Robustly)
        transcript, transcript_error = fetch_transcript_robust(video_id)
        
        if transcript == TRANSCRIPT_FALLBACK_MARKER:
            # Senior Dev: Return detailed error but still offer to analyze if possible (fallback)
            return JsonResponse({
                "status": "error", 
                "message": transcript_error,
                "video_id": video_id,
                # For debugging or future fallback logic on the frontend
                "transcript_status": "error"
            }, status=500)

        # 2. Prepare AI Prompt
        prompt = f"""
        Analyze the following YouTube video transcript. 
        Video Title: {video_title}
        Transcript: 
        ---
        {transcript[:30000]} 
        ---
        
        Your response MUST be a single, valid JSON object with the following structure:
        {{
            "summary": "A detailed, well-structured summary of the video content, formatted in markdown.",
            "quiz": [
                {{
                    "question": "Multiple choice question related to the content.",
                    "options": [
                        "Option A",
                        "Option B",
                        "Option C",
                        "Option D"
                    ],
                    "answer": "The correct option text (e.g., Option A)"
                }},
                // Add 4 more questions for a total of 5
                ...
            ]
        }}
        Ensure the JSON is perfectly valid and contains no extra text outside the JSON object.
        """
        
        # 3. Generate AI Content (Robustly)
        ai_response_text, ai_error = generate_ai_content_robust(prompt)
        
        if not ai_response_text:
            return JsonResponse({"status": "error", "message": f"AI Generation Failed: {ai_error}"}, status=500)
            
        # 4. Parse AI Response
        try:
            # Senior Dev: Clean the response, sometimes LLMs add markdown fences
            ai_response_text = ai_response_text.strip().lstrip('```json').rstrip('```')
            ai_data = json.loads(ai_response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI JSON: {ai_response_text[:500]}... Error: {e}")
            return JsonResponse({"status": "error", "message": f"AI returned an invalid JSON format. Please try again. Raw error: {e}"}, status=500)

        # 5. Success Response
        return JsonResponse({
            "status": "success",
            "summary": ai_data.get('summary', 'No summary generated.'),
            "quiz": ai_data.get('quiz', []),
            "video_id": video_id,
            "video_title": video_title,
        })

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON format in request body."}, status=400)
    except Exception as e:
        logger.exception(f"Critical error during video analysis: {e}")
        return JsonResponse({"status": "error", "message": f"A critical server error occurred: {e}"}, status=500)


@require_http_methods(["POST"])
@login_required # Assuming user authentication is desirable for AI endpoints
def submit_quiz_api(request):
    """
    Scores the quiz and generates a PDF report.
    """
    try:
        data = json.loads(request.body.decode('utf-8'))
        submitted_answers = data.get('submitted_answers', [])
        correct_answers = data.get('correct_answers', [])
        video_title = data.get('video_title', 'Analysis Report')
        summary = data.get('summary', 'No summary provided.')

        if not submitted_answers or not correct_answers:
             return JsonResponse({"status": "error", "message": "Submitted answers or correct answers are missing."}, status=400)

        final_score = 0
        quiz_results = []
        total_questions = len(correct_answers)

        # 1. Score the quiz
        for i in range(total_questions):
            correct_item = correct_answers[i]
            submitted_item = submitted_answers[i]
            
            question_text = correct_item.get('question', f'Question {i+1}')
            correct_answer_text = correct_item.get('answer', '')
            user_answer_text = submitted_item.get('user_answer', '')
            
            is_correct = (correct_answer_text.strip().lower() == user_answer_text.strip().lower())
            
            if is_correct:
                final_score += 1
                
            # Populate the results list for PDF generation
            quiz_results.append({
                "question": question_text,
                "user_answer": user_answer_text,
                "correct_answer": correct_answer_text,
                "is_correct": is_correct
            })

        # 2. Generate PDF
        pdf_content, pdf_error = create_video_analysis_pdf(
            video_title=video_title,
            summary=summary,
            quiz_results=quiz_results,
            final_score=final_score,
            total_questions=total_questions
        )
        
        if pdf_content is None:
            # Return JSON response if PDF generation failed
            return JsonResponse({
                "status": "warning", 
                "message": f"Quiz scored successfully ({final_score}/{total_questions}), but PDF generation failed: {pdf_error}",
                "final_score": final_score,
                "total_questions": total_questions,
                "quiz_results": quiz_results
            }, status=200)

        # 3. Create PDF HTTP Response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        # Ensure the filename is safe
        safe_title = video_title.replace(' ', '_').replace('/', '-').replace(':', '')
        response['Content-Disposition'] = f'attachment; filename="{safe_title}_Report.pdf"'
        
        # Add custom headers so the frontend can display the score before/after download
        response['X-Quiz-Score'] = f'{final_score}/{total_questions}'
        
        return response

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON format in quiz submission."}, status=400)
    except Exception as e:
        logger.exception(f"Error during quiz submission or PDF generation: {e}")
        return JsonResponse({"status": "error", "message": f"A server error occurred during scoring/PDF generation: {e}"}, status=500)


# --- Static Pages Views ---
def privacy_policy(request): return render(request, 'privacy.html')
def terms_conditions(request): return render(request, 'terms.html')
def about_us(request): return render(request, 'about.html')
def contact_us(request): return render(request, 'contact.html')
def sitemap_page(request): return render(request, 'sitemap-page.html')
def learnflow_overview(request): return render(request, 'learnflow_overview.html')

def learnflow_video_analysis(request):
    """The main view for the video analysis page."""
    context = {}
    return render(request, 'learnflow.html', context)
    
def video_analysis_view(request, video_id):
    """
    View to handle direct links to a video analysis page by pre-populating the URL field.
    """
    # Create a YouTube URL from the ID for the template context
    video_link = f"https://www.youtube.com/watch?v={video_id}"
    context = {'pre_loaded_video_link': video_link}
    return render(request, 'learnflow.html', context)