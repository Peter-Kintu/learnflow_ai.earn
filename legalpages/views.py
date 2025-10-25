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
        client = genai.Client(api_key=GEMINI_API_KEY)
        # Use a model that supports function calling (or text generation)
        # For general chat/summary, gemini-2.5-flash is a good choice.
        MODEL_NAME = "gemini-2.5-flash"
    else:
        client = None
        logger.error("GEMINI_API_KEY not found in environment variables.")
except Exception as e:
    client = None
    logger.error(f"Error initializing Gemini client: {e}")

# --- Helper Functions (keep them as they were) ---

def extract_youtube_id(url):
    """
    Extracts the unique YouTube video ID from various URL formats.
    """
    if not url:
        return None
    
    # Check if the input is already a video ID (alphanumeric, 11 chars)
    if len(url) == 11 and url.isalnum():
        return url

    # Parse the URL
    parsed_url = urlparse(url)
    
    # Check for standard watch format: ?v=VIDEO_ID
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
        query_params = parse_qs(parsed_url.query)
        if 'v' in query_params:
            return query_params['v'][0]
    
    # Check for short URL format: youtu.be/VIDEO_ID
    elif parsed_url.hostname == 'youtu.be':
        # The path should be '/VIDEO_ID'
        path = parsed_url.path.lstrip('/')
        if path:
            return path
            
    return None

def fetch_transcript_with_retry(video_id):
    """
    Fetches the transcript with retry logic for intermittent network or API errors.
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Fetches a list of transcript objects (usually one, or one per language)
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Prioritize English. If not available, use any available transcript.
            try:
                # Try to get the English transcript
                transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
            except NoTranscriptFound:
                # If English isn't available, try to fetch the first available one
                # Note: This might not be English, so the model response quality may vary
                transcript = transcript_list.find_transcript(transcript_list._generated_transcripts.keys())

            # Fetch the actual text
            full_transcript_text = ' '.join([item['text'] for item in transcript.fetch()])
            return full_transcript_text
            
        # Catch specific exceptions for clearer error handling
        except VideoUnavailable:
            logger.warning(f"Video {video_id} is unavailable or private.")
            return "VideoUnavailable"
        except TranscriptsDisabled:
            logger.warning(f"Transcripts are disabled for video {video_id}.")
            return "TranscriptsDisabled"
        except NoTranscriptFound:
            logger.warning(f"No transcript found for video {video_id}.")
            return "NoTranscriptFound"
        except CouldNotRetrieveTranscript as e:
            logger.warning(f"Attempt {attempt + 1}: Could not retrieve transcript for {video_id}. Retrying in 2 seconds. Error: {e}")
            time.sleep(2)
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}: An unexpected error occurred while fetching transcript for {video_id}: {e}")
            time.sleep(2)

    logger.error(f"Failed to fetch transcript for {video_id} after {MAX_RETRIES} attempts.")
    return TRANSCRIPT_FALLBACK_MARKER

# --- Gemini API Calls ---

def call_gemini_api(prompt, system_instruction, max_tokens=2048):
    """
    Generic function to call the Gemini API with standard safety and configuration.
    """
    if not client:
        return {"status": "error", "message": "AI client not initialized. Check API Key configuration."}, None

    try:
        # Configuration for safety and generation settings
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.4,
            max_output_tokens=max_tokens,
            safety_settings=[
                types.SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                    threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
                types.SafetySetting(
                    category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                    threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
                ),
            ],
        )

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=config
        )

        if response.candidates and response.candidates[0].finish_reason == types.FinishReason.SAFETY:
            return {"status": "error", "message": "Request blocked due to safety settings."}, None
            
        return {"status": "success"}, response.text

    except APIError as e:
        logger.error(f"Gemini API Error: {e}")
        return {"status": "error", "message": f"AI API Error: {e}"}, None
    except Exception as e:
        logger.error(f"An unexpected error occurred during AI call: {e}")
        return {"status": "error", "message": f"An unexpected AI error occurred: {e}"}, None

# --- Main Logic Views ---

@require_http_methods(["POST"])
@csrf_exempt
def analyze_video_api(request):
    """
    API endpoint to receive a YouTube URL, fetch transcript, and analyze the content.
    """
    try:
        data = json.loads(request.body)
        video_url = data.get('video_url', '').strip()

        if not video_url:
            return JsonResponse({"status": "error", "message": "Video URL is required."}, status=400)

        video_id = extract_youtube_id(video_url)
        if not video_id:
            return JsonResponse({"status": "error", "message": "Invalid or unsupported YouTube URL format."}, status=400)

        # 1. Fetch Transcript
        transcript_result = fetch_transcript_with_retry(video_id)

        if transcript_result == "VideoUnavailable":
            return JsonResponse({"status": "error", "message": "Video is unavailable, private, or has been removed."}, status=404)
        elif transcript_result == "TranscriptsDisabled":
            return JsonResponse({"status": "error", "message": "Transcripts are disabled for this video."}, status=404)
        elif transcript_result == "NoTranscriptFound":
            return JsonResponse({"status": "error", "message": "No English (or other) transcript found for this video."}, status=404)
        elif transcript_result == TRANSCRIPT_FALLBACK_MARKER:
            return JsonResponse({"status": "error", "message": "Failed to fetch video transcript after multiple attempts."}, status=500)
        
        # Transcript successfully fetched
        transcript = transcript_result

        # 2. Prepare AI Prompts and Call
        system_instruction = (
            "You are LearnFlow AI, an expert educational content analyzer. "
            "Your task is to analyze a video transcript and provide a structured JSON response. "
            "Strictly follow the JSON schema provided. Do not include any text, headers, or explanations outside the JSON block."
        )

        prompt = (
            f"Analyze the following video transcript. The transcript is: \"{transcript}\". "
            "Generate a comprehensive summary, a list of 5 key concepts with brief explanations, "
            "and a 3-question multiple-choice quiz based ONLY on the content. "
            "The output MUST be a single JSON object. "
            "JSON Schema: "
            "{ "
            "  \"summary\": \"[Comprehensive summary of the video content]\", "
            "  \"key_concepts\": [ "
            "    {\"concept\": \"[Concept 1 Name]\", \"explanation\": \"[Brief explanation]\"}, "
            "    // ... 4 more concepts "
            "  ], "
            "  \"quiz\": [ "
            "    { "
            "      \"question\": \"[Question 1]\", "
            "      \"options\": {\"A\": \"[Option A]\", \"B\": \"[Option B]\", \"C\": \"[Option C]\", \"D\": \"[Option D]\"}, "
            "      \"correct_answer\": \"[A|B|C|D]\" "
            "    }, "
            "    // ... 2 more questions "
            "  ] "
            "}"
        )

        status, ai_response_text = call_gemini_api(prompt, system_instruction)

        if status["status"] == "error":
            return JsonResponse(status, status=500)

        # 3. Parse and Return AI Response
        try:
            # The AI is instructed to return *only* JSON, so we strip any leading/trailing whitespace or markdown.
            cleaned_response = ai_response_text.strip().lstrip('```json').rstrip('```').strip()
            ai_data = json.loads(cleaned_response)
            
            # Check for basic structure
            if not all(k in ai_data for k in ['summary', 'key_concepts', 'quiz']):
                raise ValueError("AI response structure is invalid.")

            # Return the video analysis data
            return JsonResponse({
                "status": "success",
                "summary": ai_data['summary'],
                "key_concepts": ai_data['key_concepts'],
                "quiz": ai_data['quiz'],
                "video_id": video_id,
                "video_url": f"https://www.youtube.com/embed/{video_id}" # For the iframe
            })

        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Error parsing AI JSON response: {e}. Raw response: {ai_response_text}")
            return JsonResponse({"status": "error", "message": "AI returned an unreadable or incorrectly structured response."}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON format in request body."}, status=400)
    except Exception as e:
        logger.exception(f"Unexpected error during video analysis: {e}")
        return JsonResponse({"status": "error", "message": f"A server error occurred: {e}"}, status=500)


# --- PDF Generation Helper ---

def generate_pdf_report(quiz_data, final_score, total_questions):
    """
    Generates a PDF report of the quiz results using ReportLab.
    """
    if not PDF_ENABLED:
        logger.warning("PDF generation requested but ReportLab is not installed.")
        # Return a mock PDF content (simple text)
        buffer = BytesIO()
        buffer.write(b"PDF generation is disabled: ReportLab library is missing.")
        buffer.seek(0)
        return buffer

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                            title="LearnFlow AI Quiz Report",
                            leftMargin=40, rightMargin=40,
                            topMargin=40, bottomMargin=40)
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(name='Heading1Centered', alignment=1, fontSize=18, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='Question', fontSize=12, fontName='Helvetica-Bold', spaceAfter=6))
    styles.add(ParagraphStyle(name='Option', fontSize=10, fontName='Helvetica', leftIndent=20))
    styles.add(ParagraphStyle(name='Correct', fontSize=10, fontName='Helvetica-Bold', textColor=colors.green, spaceAfter=12, leftIndent=20))
    styles.add(ParagraphStyle(name='Incorrect', fontSize=10, fontName='Helvetica-Bold', textColor=colors.red, spaceAfter=12, leftIndent=20))
    
    story = []

    # Title and Score
    story.append(Paragraph("LearnFlow AI Quiz Report", styles['Heading1Centered']))
    story.append(Spacer(1, 12))
    
    score_text = f"Final Score: {final_score} out of {total_questions}"
    score_style = styles['Heading2']
    score_style.alignment = 1 # Center
    story.append(Paragraph(score_text, score_style))
    story.append(Spacer(1, 24))

    # Quiz Questions Review
    for i, item in enumerate(quiz_data):
        # Question
        story.append(Paragraph(f"Q{i+1}: {item['question']}", styles['Question']))
        
        # Options
        for key, value in item['options'].items():
            option_text = f"{key}. {value}"
            is_correct = key == item['correct_answer']
            is_user_chosen = key == item.get('user_answer')
            
            style_name = 'Option'
            if is_correct and is_user_chosen:
                style_name = 'Correct'
                option_text += " (Correct & Your Answer ✅)"
            elif is_correct:
                style_name = 'Correct'
                option_text += " (Correct Answer)"
            elif is_user_chosen:
                style_name = 'Incorrect'
                option_text += " (Your Incorrect Answer ❌)"
            
            story.append(Paragraph(option_text, styles[style_name]))

        story.append(Spacer(1, 6))

    doc.build(story)
    
    buffer.seek(0)
    return buffer

# --- Quiz Submission View ---

@require_http_methods(["POST"])
@csrf_exempt
def submit_quiz_api(request):
    """
    API endpoint to receive submitted quiz answers, score them, and generate a PDF report.
    """
    try:
        data = json.loads(request.body)
        submitted_quiz = data.get('submitted_quiz', [])
        
        if not submitted_quiz:
            return JsonResponse({"status": "error", "message": "No quiz data submitted."}, status=400)

        final_score = 0
        total_questions = len(submitted_quiz)

        # Score the quiz
        for question_data in submitted_quiz:
            user_answer = question_data.get('user_answer')
            correct_answer = question_data.get('correct_answer')
            
            if user_answer and user_answer == correct_answer:
                final_score += 1
        
        # 1. Generate PDF Report
        pdf_buffer = generate_pdf_report(submitted_quiz, final_score, total_questions)

        # 2. Prepare HTTP Response
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        filename = f"LearnFlow_Quiz_Report_{time.strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        # Optional: Pass score back in a custom header so the frontend can display it before/after download
        response['X-Quiz-Score'] = f'{final_score}/{total_questions}'
        
        return response

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON format in quiz submission."}, status=400)
    except Exception as e:
        logger.exception(f"Error during quiz submission or PDF generation: {e}")
        return JsonResponse({"status": "error", "message": f"A server error occurred during scoring/PDF generation: {e}"}, status=500)


# --- Static Pages Views ---
# ... (Keep all your existing static page views here)
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
    # This view accepts a video_id, validates it, and passes it to the template
    if extract_youtube_id(video_id):
        # Construct a full YouTube URL to pass to the template
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        context = {'preloaded_video_url': video_url, 'video_id': video_id}
    else:
        context = {'preloaded_video_url': '', 'video_id': None}
        
    return render(request, 'learnflow.html', context)