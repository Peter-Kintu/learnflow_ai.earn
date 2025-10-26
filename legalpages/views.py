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
    from reportlab.lib.units import inch
    PDF_ENABLED = True
except ImportError:
    logging.warning("ReportLab not installed. PDF generation will be mocked.")
    PDF_ENABLED = False


logger = logging.getLogger(__name__)

# --- Configuration ---
# You should retrieve your API key from environment variables or a secure setting
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "") 

# Initialize the client setting. The genai.Client() constructor automatically 
# picks up the API key from the environment variable or when passed explicitly.
if GEMINI_API_KEY:
    # Removed the problematic 'genai.configure(api_key=GEMINI_API_KEY)' call.
    MODEL_FLASH = "gemini-2.5-flash-preview-09-2025"
else:
    logger.error("GEMINI_API_KEY not found. AI functionality will be disabled.")
    MODEL_FLASH = None


# --- Utility Functions ---

def extract_youtube_id(url_or_id):
    """
    Extracts the YouTube video ID from a URL or returns the ID if it's already an ID.
    Handles standard watch URLs, short links, and embed formats.
    """
    if not url_or_id:
        return None
    
    # 1. Check if it's already a valid 11-char ID (a simple heuristic)
    if len(url_or_id) == 11 and all(c.isalnum() or c in ['-', '_'] for c in url_or_id):
        return url_or_id

    try:
        # 2. Parse the URL
        url_or_id = url_or_id.strip()
        parsed_url = urlparse(url_or_id)
        
        # Standard watch link: ?v=ID
        if parsed_url.hostname in ['www.youtube.com', 'youtube.com'] and parsed_url.path == '/watch':
            query = parse_qs(parsed_url.query)
            video_id = query.get('v', [None])[0]
            if video_id and len(video_id) == 11:
                return video_id
        
        # Shortened link: youtu.be/ID
        elif parsed_url.hostname == 'youtu.be':
            video_id = parsed_url.path.lstrip('/')
            if video_id and len(video_id) == 11:
                return video_id
        
        # Embed link: /embed/ID
        elif parsed_url.path.startswith('/embed/'):
            video_id = parsed_url.path.split('/embed/')[-1]
            if video_id and len(video_id) == 11:
                return video_id
                
    except Exception as e:
        logger.error(f"Error parsing URL: {e}")

    return None

def fetch_transcript(video_id):
    """Fetches the transcript for a given YouTube video ID."""
    if not video_id:
        return None, "Error: No video ID provided."
    
    try:
        # Fetching the raw transcript data
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find a human-generated transcript, then fall back to auto-generated
        transcript = None
        
        # Prioritize English, but accept any human-generated language
        for t in transcript_list:
            if t.is_generated == False:
                transcript = t
                if t.language_code == 'en':
                    break # Prefer English
        
        # Fallback to the first available auto-generated transcript if no human one is found
        if not transcript and transcript_list:
              for t in transcript_list:
                if t.is_generated == True:
                    transcript = t
                    break
        
        if not transcript:
            raise NoTranscriptFound("No suitable transcript found.")

        # Actual retrieval of the content
        full_transcript = transcript.fetch()
        
        # Format the transcript into a single string for the AI model
        text = " ".join([item['text'].replace('\n', ' ') for item in full_transcript])
        return text, None

    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video."
    except NoTranscriptFound:
        return None, "No transcript (not even auto-generated) found for this video."
    except VideoUnavailable:
        return None, "The video is unavailable or restricted."
    except CouldNotRetrieveTranscript:
        return None, "Could not retrieve the transcript (network error or unusual restriction)."
    except Exception as e:
        logger.error(f"Unexpected error during transcript fetch: {e}")
        return None, f"An unexpected error occurred: {e}"


def call_gemini_with_retry(prompt, system_instruction, response_schema=None, max_retries=3):
    """Handles Gemini API calls with exponential backoff for resilience."""
    if not MODEL_FLASH:
        return None, "API Key not configured."
    
    base_delay = 1 # seconds
    
    # Configuration for Safety (reducing the chance of blocking helpful content)
    safety_settings = [
        types.SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=HarmBlockThreshold.BLOCK_NONE,
        ),
    ]
    
    # Configuration for Generation (adding JSON structure if schema is provided)
    generation_config = {
        "safety_settings": safety_settings,
    }
    if response_schema:
        generation_config["response_mime_type"] = "application/json"
        generation_config["response_schema"] = response_schema
    
    for attempt in range(max_retries):
        try:
            # Initialize the client. It will automatically use the API key from the environment.
            client = genai.Client()
            response = client.models.generate_content(
                model=MODEL_FLASH,
                contents=prompt,
                system_instruction=system_instruction,
                config=generation_config
            )

            # Check for blocked content even if no exception was raised
            if response.prompt_feedback.block_reason:
                return None, f"Request blocked due to: {response.prompt_feedback.block_reason.name}"

            # If JSON was requested, the response.text will be a JSON string
            if response_schema:
                try:
                    return json.loads(response.text), None
                except json.JSONDecodeError:
                    logger.error(f"JSON Decode Error on attempt {attempt+1}: {response.text[:200]}")
                    # If it's the last attempt and it fails, return the raw text and an error
                    if attempt == max_retries - 1:
                        return None, "API returned unparseable JSON."
                    # Otherwise, retry
            
            # For standard text responses
            return response.text, None
            
        except APIError as e:
            if attempt < max_retries - 1:
                logger.warning(f"Gemini API Error (Attempt {attempt+1}/{max_retries}): {e}. Retrying in {base_delay * (2**attempt)}s...")
                time.sleep(base_delay * (2**attempt))
            else:
                logger.error(f"Gemini API Fatal Error: {e}")
                return None, f"Gemini API Error: {e}"
        except Exception as e:
            logger.error(f"An unexpected error occurred during API call: {e}")
            return None, f"Unexpected error: {e}"
            
    return None, "Max retries reached without successful response."


# --- PDF Generation Helper (ReportLab) ---

def generate_pdf_report(title, summary, quiz_data, action_plan):
    """Generates a PDF report from the analysis data."""
    if not PDF_ENABLED:
        return None, "PDF generation library (ReportLab) not installed."

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                             leftMargin=0.75*inch, rightMargin=0.75*inch,
                             topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    story = []

    # Define custom styles
    styles.add(ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=18, spaceAfter=20, alignment=1))
    styles.add(ParagraphStyle(name='Heading2', fontName='Helvetica-Bold', fontSize=14, spaceBefore=15, spaceAfter=8, textColor=colors.HexColor('#1a73e8')))
    styles.add(ParagraphStyle(name='BodyText', fontName='Helvetica', fontSize=10, spaceAfter=6))
    styles.add(ParagraphStyle(name='QuizQuestion', fontName='Helvetica-Bold', fontSize=11, spaceBefore=10, spaceAfter=4))
    styles.add(ParagraphStyle(name='QuizAnswer', fontName='Helvetica', fontSize=10, textColor=colors.HexColor('#006400')))
    styles.add(ParagraphStyle(name='QuizFeedback', fontName='Helvetica-Oblique', fontSize=9, textColor=colors.HexColor('#8B0000')))

    # 1. Title Page Content
    story.append(Paragraph(f"LearnFlow AI Video Analysis Report", styles['TitleStyle']))
    story.append(Paragraph(f"Video Title: <b>{title}</b>", styles['BodyText']))
    story.append(Spacer(1, 0.5 * inch))

    # 2. Summary Section
    story.append(Paragraph("---", styles['BodyText']))
    story.append(Paragraph("Key Concepts Summary", styles['Heading2']))
    # Markdown to PDF conversion is complex; keeping it simple by splitting paragraphs
    for line in summary.split('\n'):
        if line.strip():
            story.append(Paragraph(line.strip(), styles['BodyText']))
    story.append(Spacer(1, 0.2 * inch))
    
    # 3. Quiz Section (Assuming quiz_data is the full JSON response from the API)
    if quiz_data and 'score_text' in quiz_data:
        story.append(Paragraph("---", styles['BodyText']))
        story.append(Paragraph("Quiz Results and Feedback", styles['Heading2']))
        story.append(Paragraph(f"<b>Overall Score: {quiz_data.get('score_text', 'N/A')}</b>", styles['BodyText']))
        story.append(Spacer(1, 0.1 * inch))

        for item in quiz_data.get('graded_quiz', []):
            question = item.get('question', 'Question N/A')
            user_answer = item.get('user_answer', 'No Answer')
            correct_answer = item.get('correct_answer', 'N/A')
            feedback = item.get('feedback', '')
            
            story.append(Paragraph(f"Q: {question}", styles['QuizQuestion']))
            story.append(Paragraph(f"Your Answer: {user_answer}", styles['BodyText']))
            story.append(Paragraph(f"Correct Answer: {correct_answer}", styles['QuizAnswer']))
            if feedback:
                story.append(Paragraph(f"Feedback: {feedback}", styles['QuizFeedback']))
            story.append(Spacer(1, 0.1 * inch))

    # 4. Action Plan Section
    story.append(Paragraph("---", styles['BodyText']))
    story.append(Paragraph("Personalized Action Plan", styles['Heading2']))
    for line in action_plan.split('\n'):
        if line.strip():
            story.append(Paragraph(line.strip(), styles['BodyText']))

    # Build the document
    try:
        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf, None
    except Exception as e:
        logger.error(f"Error building PDF: {e}")
        return None, "Error generating PDF document."


# --- Core View Functions ---

def privacy_policy(request): return render(request, 'privacy.html')
def terms_conditions(request): return render(request, 'terms.html')
def about_us(request): return render(request, 'about.html')
def contact_us(request): return render(request, 'contact.html')
def sitemap_page(request): return render(request, 'sitemap-page.html')
def learnflow_overview(request): return render(request, 'learnflow_overview.html')

def learnflow_video_analysis(request):
    """The main view for the video analysis page."""
    # This view is for the clean path / and handles potential ?video_id= queries
    video_id = request.GET.get('video_id', '').strip()
    video_url = ''
    if extract_youtube_id(video_id):
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
    context = {
        'preloaded_video_url': video_url,
        'video_id': video_id,
        'current_path': request.path
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
        # Invalid video ID, redirect to main page without pre-loading
        context = {
            'preloaded_video_url': '',
            'video_id': '',
            'current_path': request.path # ✅ ENHANCEMENT: Added current_path
        }
        
    return render(request, 'learnflow.html', context)


# --- API Endpoints ---

@csrf_exempt
@require_http_methods(["POST"])
def analyze_video_api(request):
    """
    API endpoint to fetch transcript and generate initial analysis (summary, quiz, action plan).
    """
    try:
        data = json.loads(request.body)
        video_url = data.get('video_url', '').strip()
        video_id = extract_youtube_id(video_url)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
    except Exception as e:
        logger.error(f"Error processing input: {e}")
        return JsonResponse({"error": "Bad request format."}, status=400)
    
    if not video_id:
        return JsonResponse({"error": "Invalid or unsupported YouTube URL. Please check the link."}, status=400)
        
    # --- 1. Fetch Transcript ---
    transcript, error_message = fetch_transcript(video_id)
    if error_message:
        return JsonResponse({"error": error_message, "video_id": video_id}, status=500)
    
    # --- 2. Generate Content with Gemini ---
    
    # Define the desired structured output schema for the analysis
    analysis_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "summary": types.Schema(type=types.Type.STRING, description="A comprehensive, detailed summary of the video content, formatted in markdown with clear headings, bullet points, and bold text for key terms."),
            "quiz": types.Schema(
                type=types.Type.ARRAY,
                description="A list of 5 multiple-choice questions based on the content. Each question must have exactly 4 options (A, B, C, D) and specify the correct answer letter.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "question": types.Schema(type=types.Type.STRING),
                        "options": types.Schema(
                            type=types.Type.OBJECT,
                            properties={
                                "A": types.Schema(type=types.Type.STRING),
                                "B": types.Schema(type=types.Type.STRING),
                                "C": types.Schema(type=types.Type.STRING),
                                "D": types.Schema(type=types.Type.STRING),
                            },
                            required=['A', 'B', 'C', 'D']
                        ),
                        "correct_answer": types.Schema(type=types.Type.STRING, description="The single letter (A, B, C, or D) corresponding to the correct option.")
                    },
                    required=['question', 'options', 'correct_answer']
                )
            ),
            "action_plan": types.Schema(type=types.Type.STRING, description="A personalized, brief (3-5 point) action plan in markdown for next steps, including related topics to explore or external resources (using mock links/titles) for deeper learning.")
        },
        required=["summary", "quiz", "action_plan"]
    )
    
    # System Instruction: Define the AI's role
    system_instruction = (
        "You are LearnFlow AI, an expert educational content analyst. Your task is to process the "
        "provided YouTube video transcript and generate a structured JSON object containing: "
        "1. A detailed, multi-paragraph summary of the key concepts (in Markdown). "
        "2. A multiple-choice quiz of 5 questions with 4 options each. "
        "3. A 3-5 point action plan for further study (in Markdown). "
        "All output must adhere strictly to the provided JSON schema."
    )
    
    # User Prompt: The data to be analyzed
    prompt = f"Analyze the following video transcript and generate the required content:\n\nTRANSCRIPT:\n{transcript}"
    
    logger.info(f"Calling Gemini for analysis of video ID: {video_id}...")
    
    analysis_result, api_error = call_gemini_with_retry(
        prompt=prompt, 
        system_instruction=system_instruction, 
        response_schema=analysis_schema
    )
    
    if api_error:
        return JsonResponse({"error": f"AI Generation Failed: {api_error}"}, status=500)
    
    if not analysis_result:
          return JsonResponse({"error": "AI response was empty."}, status=500)
    
    # Check if the result matches the expected structure
    if not all(key in analysis_result for key in ["summary", "quiz", "action_plan"]):
        logger.error(f"AI returned incomplete data structure: {analysis_result}")
        return JsonResponse({"error": "AI returned an incomplete data structure."}, status=500)
        
    # --- 3. Success Response ---
    response_data = {
        "success": True,
        "video_id": video_id,
        # The AI response is already a dict/JSON object
        "analysis_data": analysis_result 
    }
    
    return JsonResponse(response_data)

@csrf_exempt
@require_http_methods(["POST"])
def submit_quiz_api(request):
    """
    API endpoint to grade the user's quiz answers using Gemini.
    """
    try:
        data = json.loads(request.body)
        quiz = data.get('quiz')
        user_answers = data.get('user_answers')
        video_title = data.get('video_title')
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)

    if not quiz or not user_answers:
        return JsonResponse({"error": "Missing quiz data or user answers."}, status=400)
    
    # Combine quiz and user answers for the AI prompt
    grading_input = []
    for q in quiz:
        # Assuming the client sends the question itself as a unique identifier for mapping
        # Since the question structure is rich, we can just use its index or a synthetic ID.
        # For simplicity in this back-end, we assume the quiz and answers are aligned by index/order.
        question_id = str(q.get('question_id')) # Ensure question_id is a string key
        user_answer_letter = user_answers.get(question_id)
        
        # Find the text of the user's selected answer
        user_answer_text = q['options'].get(user_answer_letter, f"Answered '{user_answer_letter}'")

        grading_input.append({
            "question": q.get('question'),
            "options": q.get('options'),
            "user_answer_letter": user_answer_letter,
            "user_answer_text": user_answer_text,
            "correct_answer_letter": q.get('correct_answer')
        })

    # Structured Schema for Grading Output
    grading_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "score_text": types.Schema(type=types.Type.STRING, description="A friendly summary sentence of the overall score (e.g., 'Great job! You scored 4 out of 5!')."),
            "graded_quiz": types.Schema(
                type=types.Type.ARRAY,
                description="A list of the original questions, user answers, and detailed grading feedback.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "question": types.Schema(type=types.Type.STRING),
                        "user_answer": types.Schema(type=types.Type.STRING, description="The text of the option the user selected."),
                        "correct_answer": types.Schema(type=types.Type.STRING, description="The correct answer text (not just the letter)."),
                        "is_correct": types.Schema(type=types.Type.BOOLEAN, description="True if the user's answer matches the correct one."),
                        "feedback": types.Schema(type=types.Type.STRING, description="A 1-2 sentence explanation of why the answer is correct or what the user missed.")
                    },
                    required=['question', 'user_answer', 'correct_answer', 'is_correct', 'feedback']
                )
            )
        },
        required=["score_text", "graded_quiz"]
    )

    # System Instruction: Define the AI's role
    system_instruction = (
        "You are a dedicated and encouraging academic tutor. Your task is to grade the provided quiz results. "
        "Analyze the questions, the user's choice, and the correct answer. "
        "For each question, provide detailed, supportive feedback. "
        "The entire output must adhere strictly to the provided JSON schema."
    )
    
    # User Prompt: The data to be graded
    prompt = (
        f"Grade the following user answers for a quiz based on the video: '{video_title}'. "
        f"Input Data:\n{json.dumps(grading_input, indent=2)}"
    )

    logger.info("Calling Gemini for quiz grading...")
    
    grading_result, api_error = call_gemini_with_retry(
        prompt=prompt, 
        system_instruction=system_instruction, 
        response_schema=grading_schema
    )
    
    if api_error:
        return JsonResponse({"error": f"AI Grading Failed: {api_error}"}, status=500)
        
    return JsonResponse({"success": True, "grading_data": grading_result})

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
    sanitized_title = title.replace(' ', '_').replace('/', '_')[:50]
    response['Content-Disposition'] = f'attachment; filename="{sanitized_title}_LearnFlow_Report.pdf"'
    
    return response
