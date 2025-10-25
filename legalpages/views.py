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
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    
    # Configure Generative Model Safety Settings
    safety_settings = [
        types.SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=HarmBlockThreshold.BLOCK_NONE
        ),
        types.SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=HarmBlockThreshold.BLOCK_NONE
        ),
        types.SafetySetting(
            category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=HarmBlockThreshold.BLOCK_NONE
        ),
        types.SafetySetting(
            category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=HarmBlockThreshold.BLOCK_NONE
        ),
    ]

    GEMINI_CLIENT = genai.Client(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = 'gemini-2.5-flash'
    # Use a global variable to store the safety-configured model 
    # for cleaner function calls
    GEMINI_CONFIG = types.GenerateContentConfig(
        safety_settings=safety_settings
    )

    logger.info("Gemini client initialized successfully.")

except Exception as e:
    logger.error(f"Failed to initialize Gemini client: {e}")
    GEMINI_CLIENT = None
    GEMINI_MODEL = None
    GEMINI_CONFIG = None


# --- Helper Functions ---

def extract_youtube_id(url_or_id):
    """
    Extracts the YouTube video ID from a URL or validates if it's already an ID.
    Returns the ID (str) or None if invalid.
    """
    if 'youtube.com' in url_or_id or 'youtu.be' in url_or_id:
        # Handle standard URL
        if 'v=' in url_or_id:
            return parse_qs(urlparse(url_or_id).query).get('v', [None])[0]
        # Handle short URL (youtu.be)
        path = urlparse(url_or_id).path.strip('/')
        if len(path) == 11 and not ('=' in path or '?' in path):
            return path
    elif len(url_or_id) == 11 and all(c.isalnum() or c in '-_' for c in url_or_id):
        # Assume it's already an ID (YouTube IDs are 11 characters, alphanumeric, can include - and _)
        return url_or_id
    return None

def fetch_transcript(video_id):
    """
    Fetches the transcript for a given video ID, including a retry mechanism.
    """
    for attempt in range(MAX_RETRIES):
        try:
            # Prioritize auto-generated, then fall back to any language
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # 1. Try English (en) - auto-generated
            try:
                transcript = transcript_list.find_generated_transcript(['en', 'a.en'])
                return transcript.fetch()
            except NoTranscriptFound:
                pass # Continue to next fallback

            # 2. Try the primary available language (often the best)
            if transcript_list:
                 # Fetch the first transcript available 
                return transcript_list[0].fetch()
            
            # If nothing found after checks
            logger.warning(f"No transcripts found for video ID: {video_id}")
            return None

        except (TranscriptsDisabled, VideoUnavailable) as e:
            logger.warning(f"Transcripts disabled or video unavailable for {video_id}: {e}")
            return None # Cannot proceed
        except CouldNotRetrieveTranscript:
            logger.warning(f"Attempt {attempt + 1} failed to retrieve transcript for {video_id}. Retrying...")
            time.sleep(1) # Wait before retrying
        except Exception as e:
            logger.error(f"Unhandled error fetching transcript for {video_id}: {e}")
            return None
            
    return None # All retries failed

def generate_content(prompt_template, transcript_text):
    """
    Sends the transcript and a prompt to the Gemini API and returns the response text.
    """
    full_prompt = prompt_template.format(transcript=transcript_text)
    
    try:
        response = GEMINI_CLIENT.models.generate_content(
            model=GEMINI_MODEL,
            contents=full_prompt,
            config=GEMINI_CONFIG
        )
        # Ensure the response is not blocked and has text
        if response.text and not response.candidates[0].safety_ratings:
            return response.text
        else:
             logger.warning(f"AI response blocked or empty. Safety ratings: {response.candidates[0].safety_ratings if response.candidates else 'N/A'}")
             return "AI processing failed due to safety filters or empty response."
    except APIError as e:
        logger.error(f"Gemini API Error: {e}")
        return f"AI API Error: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in generate_content: {e}")
        return f"Unexpected Error: {e}"


def generate_quiz_from_transcript(transcript_text):
    """
    Uses Gemini to generate a quiz from the video transcript.
    """
    prompt = """
    You are an expert educational AI. Generate a quiz based on the following video transcript. 
    The quiz must be a JSON object with the following structure:
    {{
        "quiz_title": "Quiz Title based on Video Topic",
        "questions": [
            {{
                "id": 1,
                "question": "The question text.",
                "options": [
                    "Option A",
                    "Option B",
                    "Option C",
                    "Option D"
                ],
                "answer": "Option A"
            }},
            // ... more questions
        ]
    }}
    The quiz must contain at least 5 multiple-choice questions. Ensure the output is *only* the raw JSON object.

    TRANSCRIPT:
    ---
    {{transcript}}
    ---
    """
    return generate_content(prompt, transcript_text)

def generate_summary_from_transcript(transcript_text):
    """
    Uses Gemini to generate a summary and key takeaways from the video transcript.
    """
    prompt = """
    You are an expert educational AI. Analyze the following video transcript and provide:
    1. A concise, engaging **Summary** of the video content.
    2. A bulleted list of at least five **Key Takeaways**.
    3. A short, compelling **Title** for the video.
    Format the output using markdown.

    TRANSCRIPT:
    ---
    {{transcript}}
    ---
    """
    return generate_content(prompt, transcript_text)


def generate_video_report_pdf(response_data, quiz_submission_data, final_score, total_questions):
    """
    Generates a PDF report containing the video summary, quiz, and results.
    Returns a BytesIO object containing the PDF content.
    """
    buffer = BytesIO()
    
    # Use a SimpleDocTemplate for flowable content (Paragraphs, Tables, etc.)
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=50, 
        leftMargin=50, 
        topMargin=50, 
        bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    # Define a custom style for the body text
    styles.add(ParagraphStyle(name='NormalCode', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=14))
    styles.add(ParagraphStyle(name='Heading1Code', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=16, leading=20, spaceAfter=10))
    styles.add(ParagraphStyle(name='Heading2Code', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=16, spaceBefore=10, spaceAfter=5))
    
    Story = []
    
    # --- Title Page / Header ---
    Story.append(Paragraph(response_data.get('video_title', 'Video Analysis Report'), styles['Heading1Code']))
    Story.append(Paragraph(f"Analysis Date: {time.strftime('%Y-%m-%d')}", styles['NormalCode']))
    Story.append(Spacer(1, 12))
    
    # --- Summary Section ---
    Story.append(Paragraph("Summary and Key Takeaways", styles['Heading1Code']))
    
    # The summary is expected to be a markdown string with a Summary and Key Takeaways section
    summary_text = response_data.get('summary_result', '').replace('\n', '<br/>')
    Story.append(Paragraph(summary_text, styles['NormalCode']))
    Story.append(Spacer(1, 12))
    
    # --- Quiz Results Section ---
    Story.append(Paragraph("Quiz Results", styles['Heading1Code']))
    Story.append(Paragraph(f"Final Score: <font color='blue'><b>{final_score} / {total_questions}</b></font>", styles['Heading2Code']))
    Story.append(Spacer(1, 12))

    quiz_data = quiz_submission_data.get('quiz_data', {})
    user_answers = quiz_submission_data.get('user_answers', {})
    
    questions = quiz_data.get('questions', [])

    for i, q_item in enumerate(questions):
        question_text = f"{i+1}. {q_item['question']}"
        correct_answer = q_item['answer']
        user_selection = user_answers.get(str(q_item['id']), 'N/A')
        
        is_correct = (user_selection == correct_answer)
        status_color = colors.green if is_correct else colors.red
        status_text = "Correct" if is_correct else "Incorrect"
        
        # Question Paragraph
        Story.append(Paragraph(question_text, styles['Heading2Code']))

        # Answer Table
        data = [
            ["Your Answer:", user_selection, ""],
            ["Correct Answer:", correct_answer, status_text]
        ]
        
        # Apply color to the status cell
        table_style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('TEXTCOLOR', (2, 1), (2, 1), status_color),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTNAME', (2, 1), (2, 1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ])

        # Define column widths: 1.5 inch for labels, 3 inch for answers, 1 inch for status
        col_widths = [doc.width * 0.25, doc.width * 0.50, doc.width * 0.25]
        
        t = Table(data, colWidths=col_widths)
        t.setStyle(table_style)
        Story.append(t)
        Story.append(Spacer(1, 12))

    doc.build(Story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# Mock implementation if ReportLab is missing
def mock_pdf_generation(*args):
    logger.warning("Using mock PDF generation.")
    return b"Mock PDF Content - ReportLab Not Installed"


# --- API Endpoints ---

@require_http_methods(["POST"])
@csrf_exempt 
def analyze_video_api(request):
    """
    API endpoint to receive a video URL, fetch its transcript, and send it to Gemini for analysis.
    """
    if not GEMINI_CLIENT:
        logger.error("Gemini client is not initialized.")
        return JsonResponse({"status": "error", "message": "AI service is unavailable."}, status=503)

    try:
        data = json.loads(request.body)
        video_url_or_id = data.get('video_url_or_id', '').strip()

        if not video_url_or_id:
            return JsonResponse({"status": "error", "message": "Video URL or ID is required."}, status=400)

        # *** FIX APPLIED HERE ***: video_url_or_or_id corrected to video_url_or_id
        video_id = extract_youtube_id(video_url_or_id) 

        if not video_id:
            return JsonResponse({"status": "error", "message": "Invalid YouTube URL or ID."}, status=400)
        
        # 1. Fetch Transcript
        transcript_result = fetch_transcript(video_id)
        
        if transcript_result is None:
            return JsonResponse({"status": "error", "message": "Could not retrieve transcript. The video may be unavailable, have transcripts disabled, or a network error occurred."}, status=400)
        
        # 2. Process Transcript into a single string
        transcript_text = " ".join([item['text'] for item in transcript_result])
        
        # Use a marker if the transcript is effectively empty (e.g., failed to retrieve non-English)
        if not transcript_text.strip():
            transcript_text = TRANSCRIPT_FALLBACK_MARKER
        
        # 3. Generate Summary & Quiz concurrently or sequentially
        summary_text = generate_summary_from_transcript(transcript_text)
        quiz_json_string = generate_quiz_from_transcript(transcript_text)

        # 4. Attempt to parse quiz JSON
        try:
            quiz_data = json.loads(quiz_json_string)
            video_title = quiz_data.get('quiz_title', 'Video Analysis Report') # Use quiz title as video title
            # In case the AI hallucinated the entire JSON structure, provide a fallback
            if not isinstance(quiz_data.get('questions'), list):
                 raise json.JSONDecodeError("AI returned invalid quiz structure.", quiz_json_string, 0)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse quiz JSON: {quiz_json_string}")
            return JsonResponse({
                "status": "error", 
                "message": "AI failed to generate a valid quiz format. Please try another video."
            }, status=500)


        # 5. Return Success Response
        return JsonResponse({
            "status": "success",
            "video_id": video_id,
            "video_title": video_title,
            "summary_result": summary_text,
            "quiz_data": quiz_data,
        })

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON in request body."}, status=400)
    except Exception as e:
        logger.exception(f"An unexpected server error occurred: {e}")
        return JsonResponse({"status": "error", "message": f"An unexpected server error occurred: {e}"}, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def submit_quiz_api(request):
    """
    API endpoint to receive quiz submission, score it, and return a PDF report.
    """
    try:
        data = json.loads(request.body)
        user_answers = data.get('user_answers', {})
        quiz_data = data.get('quiz_data', {})
        video_response_data = data.get('video_response_data', {})

        if not user_answers or not quiz_data:
            return JsonResponse({"status": "error", "message": "Missing user answers or quiz data."}, status=400)

        # 1. Score the Quiz
        final_score = 0
        total_questions = 0
        
        for question in quiz_data.get('questions', []):
            total_questions += 1
            question_id = str(question['id']) # Keys from frontend are usually strings
            correct_answer = question.get('answer')
            user_answer = user_answers.get(question_id)
            
            if user_answer and user_answer == correct_answer:
                final_score += 1
        
        # 2. Generate PDF Report
        if PDF_ENABLED:
            pdf_content = generate_video_report_pdf(
                video_response_data, 
                {'quiz_data': quiz_data, 'user_answers': user_answers}, 
                final_score, 
                total_questions
            )
        else:
            pdf_content = mock_pdf_generation()

        # 3. Create HTTP Response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        video_title = video_response_data.get('video_title', 'Report')
        # Sanitize filename
        safe_title = "".join(c for c in video_title if c.isalnum() or c in (' ', '_')).rstrip()
        filename = f"{safe_title}_Report.pdf"
        
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        # Pass score in a custom header so the frontend can display it before/after download
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
    video_id = request.GET.get('video_id', '').strip()
    context = {
        'video_id': video_id,
        'current_path': request.path  # ✅ FIX: Added current_path
    }
    return render(request, 'learnflow.html', context)
    
def video_analysis_view(request, video_id):
    """View to handle direct links to a video analysis page by pre-populating the URL field."""
    # This view accepts a video_id, validates it, and passes it to the template
    if extract_youtube_id(video_id):
        # Construct a full YouTube URL to pass to the template
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        context = {
            'preloaded_video_url': video_url,
            'video_id': video_id,
            'current_path': request.path # ✅ ENHANCEMENT: Added current_path
        }
    else:
        context = {
            'preloaded_video_url': '',
            'video_id': None,
            'current_path': request.path # ✅ ENHANCEMENT: Added current_path
        }
    return render(request, 'learnflow.html', context)
