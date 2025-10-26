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

# Imports for Gemini AI (Correctly using the recommended Python SDK)
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

# --- Simple Static Page Views (Addressing previous AttributeError) ---

def privacy_policy(request):
    """Renders the Privacy Policy page."""
    return render(request, 'legalpages/privacy.html', {})

def terms_conditions(request):
    """Renders the Terms and Conditions page."""
    return render(request, 'legalpages/terms.html', {})

def about_us(request):
    """Renders the About Us page."""
    return render(request, 'legalpages/about.html', {})

def contact_us(request):
    """Renders the Contact Us page."""
    return render(request, 'legalpages/contact.html', {})

def sitemap_page(request):
    """Renders the Sitemap page."""
    return render(request, 'legalpages/sitemap.html', {})

# --- Main Application Views ---

def learnflow_overview(request):
    """Renders the LearnFlow AI Overview/Dashboard page."""
    return render(request, 'learnflow/overview.html', {}) 

def learnflow_video_analysis(request):
    """Renders the main video analysis tool (the home page)."""
    return render(request, 'learnflow.html', {}) 

def video_analysis_view(request, video_id):
    """
    Renders a specific video analysis page based on a URL parameter.
    """
    context = {
        'video_id': video_id,
        'initial_url': f'https://www.youtube.com/watch?v={video_id}'
    }
    return render(request, 'learnflow.html', context)


# --- Utility Functions for Transcript and AI Processing ---

def get_transcript_from_youtube(video_id):
    """
    Fetches the transcript for a given YouTube video ID, handling errors gracefully.
    Returns (transcript_text, error_message).
    """
    try:
        # NOTE: Langs are ordered by preference (English primary, then fallback to other auto-generated)
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, 
            languages=['en', 'a.en', 'es', 'a.es', 'de', 'a.de', 'fr', 'a.fr']
        )
        # Combine transcript parts into a single string
        transcript_text = ' '.join([item['text'] for item in transcript_list])
        return transcript_text, None

    except NoTranscriptFound:
        return None, "No suitable transcript found for this video ID. Try another language or video."
    except TranscriptsDisabled:
        return None, "Transcripts are disabled for this video."
    except VideoUnavailable:
        return None, "Video is unavailable or has been deleted."
    except CouldNotRetrieveTranscript as e:
        return None, f"Could not retrieve transcript: {e}"
    except Exception as e:
        # Catch any unexpected errors (e.g., API limits, network issues)
        logging.error(f"An unexpected error occurred while fetching transcript for {video_id}: {e}")
        return None, "An unexpected error occurred during transcript retrieval."

def sanitize_filename(title, max_length=50):
    """Sanitizes a string to be safe for use as a filename."""
    # Replace spaces with underscores and remove non-word characters
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_')
    # Truncate to max_length
    return safe_title[:max_length] if safe_title else "report"


def call_gemini_api_with_retry(prompt, system_instruction=None, response_schema=None, max_retries=3):
    """
    Handles API calls to Gemini with built-in exponential backoff retry logic.
    Returns (result_text, error_message).
    """
    client = genai.Client()
    
    # Configure generation
    generation_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        # Only set response_mime_type and response_schema if schema is provided
        response_mime_type="application/json" if response_schema else "text/plain",
        response_schema=response_schema
    )

    # Safety settings for content filtering
    safety_settings = [
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

    for attempt in range(max_retries):
        try:
            # Use gemini-2.5-flash as the standard, fast, and capable model
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=generation_config,
                safety_settings=safety_settings
            )
            
            # Check for blocked content or empty response
            if not response.candidates or not response.text:
                return None, "AI response blocked due to safety settings or empty response."
                
            # The result is in the text attribute, regardless of output format (JSON/text)
            return response.text, None

        except APIError as e:
            error_message = f"Gemini API Error (Attempt {attempt+1}/{max_retries}): {e}"
            logging.warning(error_message)
            if attempt < max_retries - 1:
                # Exponential backoff: 2^attempt seconds
                sleep_time = 2 ** attempt
                time.sleep(sleep_time)
                continue
            return None, f"Final Gemini API failure: {error_message}"
        except Exception as e:
            error_message = f"An unexpected error occurred during API call: {e}"
            logging.error(error_message)
            return None, error_message
            
    return None, "Exceeded maximum retry attempts for Gemini API call."


def generate_pdf_report(title, summary, quiz_data, action_plan):
    """
    Generates a PDF report using ReportLab.
    Returns (pdf_content_bytes, error_message).
    """
    
    if not PDF_ENABLED:
        return None, "PDF generation library (ReportLab) is not installed."
        
    buffer = BytesIO()
    
    # Use A4 for standard document size
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=inch/2,
        leftMargin=inch/2,
        topMargin=inch/2,
        bottomMargin=inch/2
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    styles.add(ParagraphStyle(name='TitleStyle', fontName='Helvetica-Bold', fontSize=20, alignment=1, spaceAfter=20))
    styles.add(ParagraphStyle(name='Heading1', fontName='Helvetica-Bold', fontSize=14, spaceBefore=15, spaceAfter=8, textColor=colors.blue))
    styles.add(ParagraphStyle(name='Normal', fontName='Helvetica', fontSize=10, spaceAfter=8))
    styles.add(ParagraphStyle(name='Question', fontName='Helvetica-Bold', fontSize=10, spaceAfter=4))
    styles.add(ParagraphStyle(name='Answer', fontName='Helvetica', fontSize=10, spaceBefore=2, spaceAfter=10))

    story = []
    
    # Report Title
    story.append(Paragraph(title, styles['TitleStyle']))
    story.append(Paragraph("Generated by LearnFlow AI", styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    # Summary Section
    story.append(Paragraph("--- SUMMARY ---", styles['Heading1']))
    # Summary often contains markdown, but ReportLab doesn't interpret it directly.
    story.append(Paragraph(summary, styles['Normal'])) 
    story.append(Spacer(1, 0.2 * inch))

    # Quiz Results Section
    story.append(Paragraph("--- QUIZ RESULTS ---", styles['Heading1']))

    quiz_results_found = False
    if quiz_data and quiz_data.get('questions'):
        quiz_results_found = True
        for i, q in enumerate(quiz_data['questions']):
            story.append(Paragraph(f"Question {i+1}: {q['question']}", styles['Question']))
            
            # Format user answer and correct answer
            user_answer = q.get('user_answer', 'N/A')
            correct_answer = q.get('correct_answer', 'N/A')
            is_correct = q.get('is_correct', False)

            status_color = colors.green.hexa() if is_correct else colors.red.hexa()
            
            story.append(Paragraph(f"Your Answer: <font color='{status_color}'>{user_answer} ({'CORRECT' if is_correct else 'INCORRECT'})</font>", styles['Answer']))
            
            if not is_correct:
                story.append(Paragraph(f"Correct Answer: {correct_answer}", styles['Answer']))
            
            story.append(Spacer(1, 0.05 * inch))

        # Overall Score
        score = quiz_data.get('score', 'N/A')
        total = quiz_data.get('total_questions', 'N/A')
        story.append(Paragraph(f"OVERALL SCORE: {score} / {total}", styles['Heading1']))
        story.append(Spacer(1, 0.2 * inch))
    
    if not quiz_results_found:
        story.append(Paragraph("No graded quiz data available to report.", styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

    # Action Plan Section
    story.append(Paragraph("--- PERSONALIZED ACTION PLAN ---", styles['Heading1']))
    story.append(Paragraph(action_plan, styles['Normal']))
    story.append(Spacer(1, 0.2 * inch))

    try:
        doc.build(story)
        pdf_content = buffer.getvalue()
        buffer.close()
        return pdf_content, None
    except Exception as e:
        logging.error(f"Error during PDF generation: {e}")
        return None, f"Error generating PDF document: {e}"


# --- API Endpoints ---

@csrf_exempt
@require_http_methods(["POST"])
def analyze_video_api(request):
    """
    API endpoint to fetch a YouTube transcript and generate the summary, quiz,
    and action plan using the Gemini API.
    """
    try:
        data = json.loads(request.body)
        video_url = data.get('video_url')
        video_title = data.get('video_title')

        if not video_url or not video_title:
            return JsonResponse({"error": "Missing video_url or video_title."}, status=400)
            
        # 1. Extract video ID
        parsed_url = urlparse(video_url)
        video_id = None
        
        # Standard query parameter 'v' or short URL format
        if 'v' in parse_qs(parsed_url.query):
            video_id = parse_qs(parsed_url.query)['v'][0]
        elif parsed_url.netloc == 'youtu.be' and parsed_url.path:
            video_id = parsed_url.path.strip('/')

        if not video_id:
            return JsonResponse({"error": "Invalid or unsupported video URL format. Please use a standard YouTube link."}, status=400)

        # 2. Get Transcript
        transcript_text, transcript_error = get_transcript_from_youtube(video_id)
        if transcript_error:
            return JsonResponse({"error": f"Transcript Error: {transcript_error}"}, status=500)
            
        # 3. Define the desired output structure for the AI
        analysis_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "summary": types.Schema(
                    type=types.Type.STRING, 
                    description="A detailed, comprehensive summary of the video content formatted using markdown headings and bullet points."
                ),
                "quiz": types.Schema(
                    type=types.Type.ARRAY,
                    description="A list of 5 multiple-choice questions about the content.",
                    items=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "question": types.Schema(type=types.Type.STRING),
                            "options": types.Schema(type=types.Type.ARRAY, items=types.Schema(type=types.Type.STRING)),
                            "correct_answer": types.Schema(type=types.Type.STRING, description="The text of the correct option."),
                        }
                    )
                ),
                "action_plan": types.Schema(
                    type=types.Type.STRING,
                    description="A personalized, 3-step action plan in markdown format, suggesting next steps or external resources for deeper learning."
                )
            },
            required=["summary", "quiz", "action_plan"]
        )

        # 4. Define the prompt for the AI
        system_instruction = (
            "You are an expert educational AI, LearnFlow. Your task is to analyze the provided video transcript and generate "
            "a comprehensive summary, a five-question multiple-choice quiz (with 4 options per question), "
            "and a personalized action plan for further study. The summary and action plan must be formatted using markdown. "
            "Respond only with a single JSON object that strictly conforms to the provided schema. Do not include any introductory or concluding text outside the JSON."
        )
        
        prompt = (
            f"Video Title: {video_title}\n\n"
            f"Transcript:\n---\n{transcript_text}\n---\n\n"
            "Analyze the content and generate the structured JSON output containing the 'summary', 'quiz', and 'action_plan'."
        )

        # 5. Call the Gemini API
        ai_result_str, api_error = call_gemini_api_with_retry(
            prompt=prompt, 
            system_instruction=system_instruction, 
            response_schema=analysis_schema
        )
        
        if api_error:
            return JsonResponse({"error": f"AI Generation Failed: {api_error}"}, status=500)
        
        # 6. Parse the JSON result
        try:
            ai_result = json.loads(ai_result_str)
        except json.JSONDecodeError:
            logging.error(f"Failed to decode JSON from AI: {ai_result_str}")
            return JsonResponse({"error": "AI returned invalid JSON format. Please try again."}, status=500)
            
        # 7. Return the results
        return JsonResponse({
            "success": True,
            "summary": ai_result.get("summary", "Error: Summary not found."),
            "quiz": ai_result.get("quiz", []),
            "action_plan": ai_result.get("action_plan", "Error: Action plan not found."),
            "video_title": video_title 
        })
        
    except Exception as e:
        logging.error(f"Unexpected error in analyze_video_api: {e}")
        return JsonResponse({"error": f"An unexpected server error occurred: {e}"}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def submit_quiz_api(request):
    """
    API endpoint to grade the user's submitted quiz data.
    The grading logic is performed by the Gemini AI to ensure accuracy and contextual evaluation.
    """
    try:
        data = json.loads(request.body)
        quiz_data = data.get('quiz_data')
        
        if not quiz_data:
            return JsonResponse({"error": "Missing quiz data."}, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)

    # 1. Define the desired output structure for grading
    grading_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "score": types.Schema(type=types.Type.INTEGER, description="The number of correct answers."),
            "total_questions": types.Schema(type=types.Type.INTEGER, description="The total number of questions."),
            "questions": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "question": types.Schema(type=types.Type.STRING),
                        "user_answer": types.Schema(type=types.Type.STRING, description="The answer submitted by the user."),
                        "correct_answer": types.Schema(type=types.Type.STRING, description="The actual correct answer."),
                        "is_correct": types.Schema(type=types.Type.BOOLEAN, description="True if user_answer matches the correct_answer, False otherwise."),
                    }
                )
            )
        },
        required=["score", "total_questions", "questions"]
    )
    
    # 2. Define the prompt for the AI
    system_instruction = (
        "You are a strict grading assistant. Your task is to evaluate the user's submitted quiz data. "
        "For each question in the input, compare the 'user_answer' to the 'correct_answer' and set the 'is_correct' flag (True/False). "
        "Calculate the total 'score' and 'total_questions'. You MUST return all fields including 'question', 'user_answer', 'correct_answer', and 'is_correct' for every question. "
        "Respond only with a single JSON object that strictly conforms to the provided schema. Do not include any introductory or concluding text outside the JSON."
    )
    
    prompt = (
        "Grade the following quiz data. The input is an array of questions. "
        "Generate the final structured grading report in the requested JSON format.\n\n"
        f"Input Quiz Data: {json.dumps(quiz_data)}"
    )
    
    # 3. Call the Gemini API
    grading_result_str, api_error = call_gemini_api_with_retry(
        prompt=prompt, 
        system_instruction=system_instruction, 
        response_schema=grading_schema
    )
    
    if api_error:
        return JsonResponse({"error": f"AI Grading Failed: {api_error}"}, status=500)
        
    # 4. Parse the JSON result
    try:
        grading_result = json.loads(grading_result_str)
    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from AI Grading: {grading_result_str}")
        return JsonResponse({"error": "AI Grading returned invalid JSON format."}, status=500)

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
    sanitized_title = sanitize_filename(title)
    response['Content-Disposition'] = f'attachment; filename="{sanitized_title}_report.pdf"'
    
    return response
