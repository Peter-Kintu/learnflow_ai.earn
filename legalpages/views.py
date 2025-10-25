import os
import logging
import time 
import json 
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
# New: Import required decorators
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlparse, parse_qs
from io import BytesIO 

# Imports for Transcript Fetching - UPDATED FOR ROBUSTNESS
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled 
# Explicitly import exceptions from the _errors submodule to resolve Pylance warnings
from youtube_transcript_api._errors import (
    CouldNotRetrieveTranscript, 
    VideoUnavailable, 
    NoTranscriptFound 
)

# Imports for Gemini AI
import google.genai as genai
from google.genai.errors import APIError
from google.genai import types 
from google.genai.types import HarmCategory, HarmBlockThreshold

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

# Initialize Gemini Client (Robustly Check API Key)
try:
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if GEMINI_API_KEY:
        # Assuming GEMINI_CLIENT initialization is robust
        # This is a placeholder as the full initialization logic is complex
        GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
        SAFETY_SETTINGS = [
            types.SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            ),
            types.SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            ),
            types.SafetySetting(
                category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            ),
            types.SafetySetting(
                category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            ),
        ]
    else:
        logger.error("GEMINI_API_KEY environment variable not set. AI features are disabled.")
        GEMINI_CLIENT = None
except Exception as e:
    logger.error(f"Error initializing Gemini client: {e}")
    GEMINI_CLIENT = None


# --- Helper Functions (Please ensure your helper functions are placed here) ---

def extract_youtube_id(url_or_id):
    """Extracts the 11-character YouTube video ID from a URL or checks if it's already an ID."""
    if len(url_or_id) == 11 and all(c.isalnum() or c in ['-', '_'] for c in url_or_id):
        return url_or_id
    try:
        if 'youtu.be' in url_or_id:
            # Handle short links
            return url_or_id.split('/')[-1].split('?')[0]
        elif 'youtube.com' in url_or_or_id:
            # Handle standard links
            query = urlparse(url_or_id).query
            video_id = parse_qs(query).get('v')
            return video_id[0] if video_id else None
    except:
        return None
    return None

def get_transcript(video_id):
    """
    Fetches the transcript for a given YouTube video ID, handling various errors.
    Returns the transcript text or TRANSCRIPT_FALLBACK_MARKER.
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Attempt to fetch both auto-generated and manual transcripts
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Prioritize English, then auto-generated English, then any available transcript
            transcript = None
            if transcript_list.find_transcript(['en']):
                transcript = transcript_list.find_transcript(['en'])
            elif transcript_list.find_transcript(['en'], exact_match=False): # Auto-generated English
                transcript = transcript_list.find_transcript(['en'], exact_match=False)
            elif transcript_list:
                # Fallback to the first available transcript
                transcript = transcript_list[0]
            
            if transcript:
                # Fetch and format the actual text
                fetched_transcript = transcript.fetch()
                return " ".join([item['text'] for item in fetched_transcript])

        # Specific exception handling for robustness
        except (TranscriptsDisabled, NoTranscriptFound):
            logger.warning(f"Transcript disabled or not found for video ID: {video_id}")
            return TRANSCRIPT_FALLBACK_MARKER
        except (CouldNotRetrieveTranscript, VideoUnavailable) as e:
            logger.error(f"Attempt {attempt + 1}: Failed to retrieve transcript for {video_id}. Error: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt) # Exponential backoff
            else:
                return TRANSCRIPT_FALLBACK_MARKER
        except Exception as e:
            logger.exception(f"Unexpected error retrieving transcript for {video_id}: {e}")
            return TRANSCRIPT_FALLBACK_MARKER

    return TRANSCRIPT_FALLBACK_MARKER # Should not be reached if MAX_RETRIES > 0

def generate_quiz(transcript):
    """Uses the Gemini API to generate a multiple-choice quiz from the transcript."""
    if not GEMINI_CLIENT:
        return {"status": "error", "message": "AI client not initialized. Check API Key."}

    prompt = f"""
    You are an expert educational assistant. Your task is to generate a challenging, five-question, multiple-choice quiz based ONLY on the provided video transcript.
    The quiz must be returned as a single JSON object.

    JSON Format Instructions:
    - The root object must contain a key 'quiz_data' which is a list of quiz questions.
    - Each item in 'quiz_data' must be an object with the following keys:
      - "question": The question text.
      - "options": A list of four strings representing the options (A, B, C, D).
      - "answer": The index (0, 1, 2, or 3) of the correct option in the 'options' list.

    Transcript to use:
    ---
    {transcript}
    ---
    """
    try:
        response = GEMINI_CLIENT.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "quiz_data": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(
                                type=types.Type.OBJECT,
                                properties={
                                    "question": types.Schema(type=types.Type.STRING),
                                    "options": types.Schema(
                                        type=types.Type.ARRAY, 
                                        items=types.Schema(type=types.Type.STRING)
                                    ),
                                    "answer": types.Schema(type=types.Type.INTEGER)
                                }
                            )
                        )
                    }
                ),
                safety_settings=SAFETY_SETTINGS,
            ),
        )
        # Parse the JSON string contained in the text field of the response
        json_data = json.loads(response.text)
        return {"status": "success", "quiz": json_data.get('quiz_data', [])}

    except APIError as e:
        logger.error(f"Gemini API Error in generate_quiz: {e}")
        return {"status": "error", "message": f"AI service error (APIError): {e}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON Decode Error in generate_quiz: {e}\nRaw Response: {response.text if 'response' in locals() else 'N/A'}")
        return {"status": "error", "message": "AI service returned improperly formatted data."}
    except Exception as e:
        logger.exception(f"Unexpected error in generate_quiz: {e}")
        return {"status": "error", "message": f"An unexpected server error occurred: {e}"}

def generate_report(transcript):
    """Uses the Gemini API to generate a summary report from the transcript."""
    if not GEMINI_CLIENT:
        return {"status": "error", "report": "AI client not initialized. Check API Key."}
    
    prompt = f"""
    Based on the following video transcript, provide a comprehensive analysis that must include:
    1. A **Detailed Summary** of the main points.
    2. A list of **3-5 Key Concepts/Vocabulary** explained briefly.
    3. **Two Thought-Provoking Questions** for discussion.

    Format your output using Markdown.

    Transcript:
    ---
    {transcript}
    ---
    """
    try:
        response = GEMINI_CLIENT.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(safety_settings=SAFETY_SETTINGS),
        )
        return {"status": "success", "report": response.text}
    except APIError as e:
        logger.error(f"Gemini API Error in generate_report: {e}")
        return {"status": "error", "report": f"AI service error (APIError): {e}"}
    except Exception as e:
        logger.exception(f"Unexpected error in generate_report: {e}")
        return {"status": "error", "report": f"An unexpected server error occurred: {e}"}

def generate_pdf_report(quiz_data, score_details):
    """
    Generates a PDF report containing the quiz questions, user answers, correct answers, 
    and the final score using ReportLab.
    Returns an HttpResponse with the PDF content.
    """
    if not PDF_ENABLED:
        logger.warning("PDF generation requested but ReportLab is not available.")
        # Return a simple JSON response indicating the PDF is skipped
        return JsonResponse({
            "status": "success", 
            "message": "PDF generation skipped: ReportLab not installed.",
            "final_score": score_details.get('final_score'),
            "total_questions": score_details.get('total_questions'),
            "video_title": score_details.get('video_title')
        })

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            leftMargin=30,
                            rightMargin=30,
                            topMargin=40,
                            bottomMargin=40)
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(name='Heading1', fontSize=18, spaceAfter=12, alignment=1))
    styles.add(ParagraphStyle(name='Heading2', fontSize=14, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name='BodyText', fontSize=10, spaceAfter=6))
    styles.add(ParagraphStyle(name='Answer', fontSize=10, textColor=colors.green, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Wrong', fontSize=10, textColor=colors.red, fontName='Helvetica-Bold'))

    Story = []

    # Title
    Story.append(Paragraph(f"LearnFlow AI Quiz Report", styles['Heading1']))
    Story.append(Paragraph(f"**Video:** {score_details.get('video_title', 'Untitled Video')}", styles['BodyText']))
    Story.append(Paragraph(f"**Score:** {score_details.get('final_score')}/{score_details.get('total_questions')}", styles['BodyText']))
    Story.append(Spacer(1, 12))
    
    # Quiz Details
    for i, item in enumerate(quiz_data):
        # Question Number and Text
        Story.append(Paragraph(f"**Question {i+1}:** {item['question']}", styles['Heading2']))
        
        # Options and Answers
        options_text = []
        for j, option in enumerate(item['options']):
            prefix = f"{chr(65+j)}." 
            style = styles['BodyText']
            
            # Highlight correct answer
            if j == item['answer']:
                style = styles['Answer']
                
            # Highlight user's selected answer if it's wrong
            elif j == item.get('user_answer_index') and j != item['answer']:
                style = styles['Wrong']
            
            options_text.append(Paragraph(f"{prefix} {option}", style))
            
        Story.extend(options_text)
        
        # Summary of user response
        user_index = item.get('user_answer_index')
        if user_index is not None:
            user_choice = chr(65 + user_index)
            is_correct = user_index == item['answer']
            correct_choice = chr(65 + item['answer'])
            
            if is_correct:
                feedback = f"Your Answer: <font color='green'>**{user_choice} (Correct)**</font>"
            else:
                feedback = f"Your Answer: <font color='red'>**{user_choice} (Incorrect)**</font>. Correct Answer: **{correct_choice}**"
            
            Story.append(Paragraph(feedback, styles['BodyText']))
        
        Story.append(Spacer(1, 12))

    # Build the document
    doc.build(Story)
    
    # FileResponse and return
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(pdf, content_type='application/pdf')
    # Use video title to create a safe file name
    title = score_details.get('video_title', 'quiz_report').replace(' ', '_').replace('/', '-')[:50]
    response['Content-Disposition'] = f'attachment; filename="{title}_quiz_report.pdf"'
    
    return response


# --- API Endpoints ---

@require_http_methods(["POST"])
@csrf_exempt # Use this with caution, or ensure proper CSRF token handling on frontend
def analyze_video_api(request):
    """
    API endpoint to receive a video URL, fetch the transcript, and generate 
    the summary and quiz using Gemini AI.
    """
    try:
        data = json.loads(request.body)
        video_url_or_id = data.get('video_link', '').strip()

        if not video_url_or_id:
            return JsonResponse({"status": "error", "message": "Video link is required."}, status=400)

        video_id = extract_youtube_id(video_url_or_or_id)
        if not video_id:
            return JsonResponse({"status": "error", "message": "Invalid YouTube URL or ID."}, status=400)
        
        # 1. Fetch Transcript
        transcript_result = get_transcript(video_id)
        
        if transcript_result == TRANSCRIPT_FALLBACK_MARKER:
             message = "Transcript unavailable for this video (disabled, not found, or private)."
             return JsonResponse({"status": "error", "message": message}, status=404)
        
        # 2. Generate Summary Report (Tab 1)
        report_data = generate_report(transcript_result)
        if report_data['status'] == 'error':
            # Log the error but continue if quiz is vital
            logger.error(f"Failed to generate report: {report_data['report']}")

        # 3. Generate Quiz (Tab 2)
        quiz_data = generate_quiz(transcript_result)
        
        if quiz_data['status'] == 'error':
             # If both report and quiz fail, return the error
             if report_data['status'] == 'error':
                return JsonResponse({"status": "error", "message": quiz_data['message']}, status=500)
             # If only quiz fails, log and continue with partial data
             logger.error(f"Failed to generate quiz: {quiz_data['message']}")
             quiz_data['quiz'] = [] # Empty quiz to signify failure
        
        # Success Response
        return JsonResponse({
            "status": "success",
            "report": report_data.get('report'),
            "quiz": quiz_data.get('quiz'),
            "video_id": video_id,
            "video_url": f"https://www.youtube.com/watch?v={video_id}",
            "video_title": data.get('video_title', 'Untitled Video') # Pass title from front-end if available
        })

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON format in request."}, status=400)
    except Exception as e:
        logger.exception(f"Error during video analysis: {e}")
        return JsonResponse({"status": "error", "message": f"A server error occurred: {e}"}, status=500)


@require_http_methods(["POST"])
@csrf_exempt # Use this with caution, or ensure proper CSRF token handling on frontend
def submit_quiz_api(request):
    """
    API endpoint to receive the submitted quiz answers, score the quiz, and 
    return a PDF report of the results.
    """
    try:
        data = json.loads(request.body)
        quiz_data = data.get('quiz_data', [])
        video_title = data.get('video_title', 'Quiz Report')

        final_score = 0
        total_questions = len(quiz_data)

        # 1. Score the quiz
        for item in quiz_data:
            correct_answer_index = item['answer']
            user_answer_index = item.get('user_answer_index') # Can be None if unanswered
            
            # Convert str answer from frontend back to int for comparison
            if isinstance(user_answer_index, str) and user_answer_index.isdigit():
                 user_answer_index = int(user_answer_index)

            # Important: Update the item with the final integer user answer for the PDF
            item['user_answer_index'] = user_answer_index

            if user_answer_index is not None and user_answer_index == correct_answer_index:
                final_score += 1
        
        score_details = {
            'final_score': final_score,
            'total_questions': total_questions,
            'video_title': video_title
        }

        # 2. Generate the PDF
        response = generate_pdf_report(quiz_data, score_details)
        
        # 3. Add score header for the frontend to display it before/after download
        # This is a custom HTTP header for status
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

# ----------------------------------------------------------------------
# VITAL UPDATE: Ensure 'current_path' is always in the context for base.html
# ----------------------------------------------------------------------

def learnflow_video_analysis(request):
    """
    The main view for the video analysis page (home page).
    ✅ FIX: Now includes 'current_path' in the context to support active navigation link logic.
    """
    context = {
        'current_path': request.path,  # **FIXED**
    }
    return render(request, 'learnflow.html', context)
    
def video_analysis_view(request, video_id):
    """
    View to handle direct links to a video analysis page by pre-populating the URL field.
    ✅ FIX: Initializes context with 'current_path' before adding video-specific data.
    """
    # Initialize context with current path for navigation logic
    context = {
        'current_path': request.path, # **FIXED**
    }

    # This view accepts a video_id, validates it, and passes it to the template
    if extract_youtube_id(video_id):
        # Construct a full YouTube URL to pass to the template
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        context['preloaded_video'] = video_url
    else:
        context['error_message'] = 'Invalid video ID provided.'

    return render(request, 'learnflow.html', context)