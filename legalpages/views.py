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


# --- TEMPORARY API KEY FOR TESTING ---
# IMPORTANT: In a production environment, this should always be loaded from a secure
# environment variable (e.g., in a settings file or OS environment) and NOT hardcoded.
GEMINI_API_KEY_FOR_TESTING = "AIzaSyAPPxFduurg61JsZTq5w9GI9HQPKHWheKo"
# --- END TEMPORARY API KEY ---


# Configure logging
logging.basicConfig(level=logging.INFO)


# --- Helper Functions for PDF Generation ---

def generate_pdf_report(title, summary, quiz_data, action_plan):
    if not PDF_ENABLED:
        return None, "PDF generation library (ReportLab) is not installed."
        
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                            leftMargin=inch/2, rightMargin=inch/2, 
                            topMargin=inch/2, bottomMargin=inch/2)
    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(name='TitleStyle', parent=styles['Heading1'], fontSize=18, spaceAfter=12, alignment=1))
    styles.add(ParagraphStyle(name='Heading2Style', parent=styles['Heading2'], fontSize=14, spaceBefore=12, spaceAfter=6, textColor=colors.HexColor('#3b82f6')))
    styles.add(ParagraphStyle(name='NormalStyle', parent=styles['Normal'], fontSize=10, leading=14))
    styles.add(ParagraphStyle(name='FeedbackStyle', parent=styles['Normal'], fontSize=9, leading=12, leftIndent=10))

    Story = []

    # 1. Title Page/Header
    Story.append(Paragraph(title, styles['TitleStyle']))
    Story.append(Paragraph("LearnFlow AI Analysis Report", styles['Heading2Style']))
    Story.append(Paragraph(f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}", styles['NormalStyle']))
    Story.append(Spacer(1, 0.5 * inch))

    # 2. Summary Section
    Story.append(Paragraph("1. Video Summary", styles['Heading2Style']))
    # Basic attempt to convert markdown-like summary to PDF flowables
    summary_lines = summary.split('\n')
    for line in summary_lines:
        if line.strip().startswith('##'):
            # Simple H2 conversion
            Story.append(Paragraph(line.strip('#').strip(), styles['Heading2Style']))
        elif line.strip().startswith('*') or line.strip().startswith('-'):
            # Bullet point handling
            Story.append(Paragraph(f"• {line.strip('*').strip('-').strip()}", styles['NormalStyle'], bulletText='•'))
        elif line.strip():
            # Standard paragraph
            Story.append(Paragraph(line, styles['NormalStyle']))
    Story.append(Spacer(1, 0.2 * inch))
    
    # 3. Quiz Results Section
    if quiz_data.get('graded_quiz'):
        Story.append(Paragraph("2. Quiz Results", styles['Heading2Style']))
        Story.append(Paragraph(quiz_data.get('score_text', 'Score not available.'), styles['NormalStyle']))
        Story.append(Spacer(1, 0.1 * inch))
        
        for i, q in enumerate(quiz_data['graded_quiz']):
            Story.append(Paragraph(f"<b>Q{i+1}:</b> {q['question']}", styles['NormalStyle']))
            
            answer_text = f"Your Answer: <b>{q['user_answer']}</b>"
            color = colors.green if q['is_correct'] else colors.red
            
            Story.append(Paragraph(answer_text, styles['NormalStyle'], textColor=color))
            Story.append(Paragraph(f"Correct Answer: <b>{q['correct_answer']}</b>", styles['NormalStyle']))
            Story.append(Paragraph(f"<i>Feedback: {q['feedback']}</i>", styles['FeedbackStyle']))
            Story.append(Spacer(1, 0.1 * inch))

    # 4. Action Plan Section
    Story.append(Paragraph("3. Learning Action Plan", styles['Heading2Style']))
    # Basic attempt to convert markdown-like action plan to PDF flowables
    action_plan_lines = action_plan.split('\n')
    for line in action_plan_lines:
        if line.strip().startswith('##'):
            Story.append(Paragraph(line.strip('#').strip(), styles['Heading2Style']))
        elif line.strip().startswith('1.'):
            # Numbered list handling (simple)
            Story.append(Paragraph(line, styles['NormalStyle']))
        elif line.strip():
            Story.append(Paragraph(line, styles['NormalStyle']))
    Story.append(Spacer(1, 0.2 * inch))


    try:
        doc.build(Story)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf, None
    except Exception as e:
        return None, f"PDF generation failed during build: {str(e)}"

# --- Helper Functions for Gemini AI ---

def run_gemini_analysis(prompt, video_transcript, system_prompt, output_schema=None):
    """
    Calls the Gemini API to generate content.
    """
    
    # Use the test key for client initialization
    try:
        # Initialize the client using the hardcoded test key
        client = genai.Client(api_key=GEMINI_API_KEY_FOR_TESTING)
    except Exception as e:
        return None, f"Could not initialize Gemini client. Error: {str(e)}"
        
    # The full prompt for the model
    full_prompt = (
        f"{system_prompt}\n\n"
        f"The following is the video transcript:\n\n---\n{video_transcript}\n---\n\n"
        f"Based on the transcript, please fulfill the request: {prompt}"
    )

    # Configuration for API call
    config = {
        "system_instruction": full_prompt,
        "temperature": 0.7,
        "max_output_tokens": 4096,
        "safety_settings": [
            types.SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            ),
            types.SafetySetting(
                category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            ),
        ]
    }
    
    if output_schema:
        config["response_mime_type"] = "application/json"
        config["response_schema"] = output_schema

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[full_prompt], # Pass the full prompt as the content
            config=config,
        )
        
        # Check if the response contains text and return it
        if response.text:
            return response.text, None
        else:
            return None, "AI generation failed or was blocked by safety settings."

    except APIError as e:
        logging.error(f"Gemini API Error: {e}")
        # The API often returns a descriptive error message in the exception string
        # We can extract and return a slightly cleaner version.
        error_message = str(e)
        if "Bad Request" in error_message and "The prompt is too long" in error_message:
             return None, "The video transcript is too long to process. Please try a shorter video."
        return None, f"AI generation failed due to API error. Details: {error_message}"
    except Exception as e:
        logging.error(f"Unexpected error during AI generation: {e}")
        return None, f"An unexpected error occurred during AI generation: {str(e)}"

# --- Helper Functions for Transcript & ID Extraction ---

def extract_video_id(url):
    """Extracts YouTube video ID from various URLs."""
    if not url:
        return None
    url_data = urlparse(url)
    query = parse_qs(url_data.query)
    if 'v' in query:
        return query['v'][0]
    if 'youtu.be' in url_data.netloc:
        return url_data.path[1:]
    return None

def get_transcript(video_id):
    """Fetches the transcript for a given video ID."""
    try:
        # Prioritize English, fall back to auto-generated if possible
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find an English (manual or auto-generated) transcript
        transcript = None
        
        # 1. Look for English
        english_transcripts = [t for t in transcript_list if t.language_code == 'en']
        if english_transcripts:
            transcript = english_transcripts[0]

        # 2. Fallback: If no English, try the first available non-translated transcript
        if not transcript:
             for t in transcript_list:
                if not t.is_translated:
                    transcript = t
                    break
                    
        # 3. Fallback: If still nothing, try the first available translation
        if not transcript and transcript_list:
             transcript = transcript_list[0]
        
        if not transcript:
            raise NoTranscriptFound("No suitable transcript found for this video.")

        # Fetch the transcript content
        transcript_data = transcript.fetch()
        full_text = " ".join([item['text'] for item in transcript_data])
        
        return full_text, None
        
    except TranscriptsDisabled:
        # This is the expected scenario for the new fallback logic.
        return None, "Transcript is disabled for this video, falling back to description/title analysis."
    except VideoUnavailable:
        return None, "Video is unavailable or has been deleted."
    except NoTranscriptFound:
        return None, "No transcript found for this video."
    except CouldNotRetrieveTranscript as e:
        # Catches various other retrieval errors
        return None, f"Could not retrieve transcript: {e}"
    except Exception as e:
        return None, f"An unexpected error occurred during transcript retrieval: {e}"

# --- Django Views ---

def learnflow_video_analysis(request):
    """Main view for the LearnFlow AI tool."""
    # Preload a video URL if passed as a query parameter (e.g., ?video=...)
    preloaded_video_url = request.GET.get('video', '')
    context = {
        'preloaded_video_url': preloaded_video_url,
        # Other context variables if needed
    }
    return render(request, 'learnflow.html', context)

def learnflow_overview(request):
     """Simple view for the product overview page."""
     return render(request, 'overview.html')

def video_analysis_view(request, video_id):
    """View to deep-link to an analysis (optional, but good for routing)."""
    video_url = f'https://www.youtube.com/watch?v={video_id}'
    # This view redirects to the main page with the video pre-loaded
    return learnflow_video_analysis(request, video=video_url)


# --- API Endpoints ---

@csrf_exempt
@require_http_methods(["POST"])
def analyze_video_api(request):
    """
    API endpoint to initiate video analysis (Summary, Quiz, Action Plan).
    
    The core logic handles the new fallback:
    1. Try to get transcript.
    2. If disabled/unavailable, return a specific error that the frontend will interpret
       to prompt the user to continue with a description-based analysis.
    3. If transcript is retrieved, proceed with detailed analysis.
    """
    
    try:
        data = json.loads(request.body)
        video_url = data.get('video_url')
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)
        
    video_id = extract_video_id(video_url)
    if not video_id:
        return JsonResponse({"error": "Invalid YouTube video link. Please check the URL format."}, status=400)

    # 1. Attempt to get the full transcript
    transcript, transcript_error = get_transcript(video_id)
    
    # 2. Handle failure to get transcript
    if transcript_error:
        # Transcript is truly mandatory for a deep analysis
        return JsonResponse({
            "error": f"Analysis failed: {transcript_error}",
        }, status=500) 
        
    # 3. Define the analysis request and schema
    analysis_prompt = (
        "Generate a comprehensive analysis of the video content based on the provided transcript. "
        "The analysis MUST be returned as a single JSON object conforming to the schema."
    )
    
    system_instruction = (
        "You are LearnFlow, a world-class AI learning assistant. Your task is to analyze a YouTube video "
        "transcript and generate three outputs: a detailed summary, a multiple-choice quiz (5 questions, 4 options each, one correct answer), "
        "and a personalized action plan. Output MUST strictly follow the provided JSON schema."
    )
    
    analysis_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "summary": types.Schema(
                type=types.Type.STRING,
                description="A detailed, comprehensive summary of the video content formatted in Markdown."
            ),
            "quiz": types.Schema(
                type=types.Type.ARRAY,
                description="A list of 5 multiple-choice questions.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "question": types.Schema(type=types.Type.STRING),
                        "options": types.Schema(
                            type=types.Type.OBJECT,
                            description="Four options (A, B, C, D) for the question.",
                            additionalProperties=types.Schema(type=types.Type.STRING)
                        ),
                        "correct_key": types.Schema(
                            type=types.Type.STRING,
                            description="The key (A, B, C, or D) corresponding to the correct answer."
                        ),
                    },
                    required=["question", "options", "correct_key"]
                )
            ),
            "action_plan": types.Schema(
                type=types.Type.STRING,
                description="A 3-5 point personalized learning action plan in Markdown, suggesting next steps, related topics, and resources."
            )
        },
        required=["summary", "quiz", "action_plan"]
    )
    
    # 4. Run the AI analysis
    json_result, api_error = run_gemini_analysis(
        prompt=analysis_prompt, 
        video_transcript=transcript,
        system_prompt=system_instruction, 
        output_schema=analysis_schema
    )
    
    if api_error:
        # Catches errors like prompt too long or AI failure
        return JsonResponse({"error": f"AI Generation Failed: {api_error}"}, status=500)
    
    try:
        # The result comes as a string JSON inside the response text
        analysis_data = json.loads(json_result)
        # Check for minimum required keys
        if not all(k in analysis_data for k in ["summary", "quiz", "action_plan"]):
            raise ValueError("AI response is incomplete or missing core fields.")
            
        return JsonResponse({"success": True, "analysis_data": analysis_data})
    
    except json.JSONDecodeError:
        logging.error(f"Failed to parse JSON from AI response: {json_result[:200]}")
        return JsonResponse({"error": "AI response was malformed. Please try again."}, status=500)
    except ValueError as e:
        logging.error(f"Incomplete AI data: {e}")
        return JsonResponse({"error": f"AI response was incomplete: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def submit_quiz_api(request):
    """
    API endpoint to submit user answers and receive graded feedback.
    """
    try:
        data = json.loads(request.body)
        quiz = data.get('quiz')
        user_answers = data.get('user_answers')
        # video_title is currently unused but kept for future context/report generation
        # video_title = data.get('video_title') 
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON format."}, status=400)

    if not quiz or not user_answers:
        return JsonResponse({"error": "Missing quiz data or user answers."}, status=400)

    # 1. Prepare data for grading
    # The JSON schema is built around a list of graded questions.
    # We must construct a prompt that includes the original question, options,
    # the user's selected key, and the correct key.
    
    grading_list = []
    
    for question_data in quiz:
        q_id = question_data.get('question_id')
        user_key = user_answers.get(q_id)
        
        # Ensure we have a valid key to grade
        if not user_key:
            continue
            
        grading_list.append({
            "question": question_data['question'],
            "user_answer": question_data['options'].get(user_key, 'N/A'),
            "correct_answer": question_data['options'].get(question_data['correct_key'], 'N/A'),
            "user_key": user_key,
            "correct_key": question_data['correct_key'],
            "is_correct": user_key == question_data['correct_key']
        })

    # Simple score calculation
    correct_count = sum(item['is_correct'] for item in grading_list)
    total_count = len(grading_list)
    
    if not grading_list:
        return JsonResponse({"error": "No questions were graded."}, status=400)
        
    score_text = f"You scored {correct_count} out of {total_count}."
    
    # 2. Define the grading request and schema
    
    grading_prompt = (
        "For each item in the provided list, which includes the question, the user's answer, and the correct answer, "
        "write a concise, helpful, and encouraging feedback comment. Do not repeat the question or the answer. "
        "Your output MUST be a JSON array where each object has a single 'feedback' field for the corresponding question."
    )

    system_instruction = (
        "You are a helpful and experienced tutor. You provide constructive and concise feedback for a student's quiz answers. "
        "Your feedback should be encouraging for correct answers and instructive for incorrect answers, pointing the student "
        "to the relevant concepts without revealing the specific answer again. Output MUST strictly follow the provided JSON schema."
    )
    
    # Define the structure of the JSON the model should return
    feedback_schema = types.Schema(
        type=types.Type.ARRAY,
        items=types.Schema(
            type=types.Type.OBJECT,
            properties={"feedback": types.Schema(type=types.Type.STRING)},
            required=["feedback"]
        )
    )

    # The content sent to the model is the list of questions and answers for which feedback is needed.
    feedback_input = json.dumps(grading_list, indent=2)

    # 3. Run the AI feedback generation
    feedback_json_result, api_error = run_gemini_analysis(
        prompt=grading_prompt, 
        video_transcript=feedback_input, # Use the grading list as "transcript" for context
        system_prompt=system_instruction, 
        output_schema=feedback_schema
    )
    
    if api_error:
        # In case of AI failure, return the score anyway without detailed feedback
        return JsonResponse({
            "success": True, 
            "grading_data": {
                "score_text": score_text,
                "graded_quiz": grading_list,
                "feedback_error": f"Feedback generation failed: {api_error}"
            }
        }, status=200) # Return 200 even with partial failure

    try:
        feedback_data = json.loads(feedback_json_result)
        
        # 4. Merge feedback into the grading list
        if len(feedback_data) == len(grading_list):
            for i in range(len(grading_list)):
                grading_list[i]['feedback'] = feedback_data[i]['feedback']
        else:
             # Fallback if AI returns wrong number of feedback items
             for item in grading_list:
                 item['feedback'] = "Generated feedback is unavailable or mismatched. Review the answer."

    except json.JSONDecodeError:
        logging.error(f"Failed to parse JSON from AI feedback: {feedback_json_result[:200]}")
        # Use a generic error message for feedback
        for item in grading_list:
            item['feedback'] = "AI feedback generation failed due to a formatting error."


    # 5. Final successful response
    grading_result = {
        "score_text": score_text,
        "graded_quiz": grading_list,
    }
        
    return JsonResponse({"success": True, "grading_data": grading_result})

@csrf_exempt
@require_http_methods(["POST"])
def export_content_api(request):
    """
    API endpoint to generate and return the PDF report.
    """
    if not PDF_ENABLED:
        return JsonResponse({"error": "PDF generation library (ReportLab) is not available on the server."}, status=500)
        
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
    # Use the video title for the filename, sanitizing it for file systems
    sanitized_title = "".join([c for c in title if c.isalnum() or c in (' ', '_')]).rstrip()
    filename = f"{sanitized_title}_Report.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response
