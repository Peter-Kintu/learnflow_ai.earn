import os
import logging
import time 
import json 
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlparse, parse_qs
from io import BytesIO # For in-memory PDF generation

# Imports for Transcript Fetching
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api._errors import CouldNotRetrieveTranscript, VideoUnavailable 

# Imports for Gemini AI
import google.genai as genai
from google.genai.errors import APIError
from google.genai import types 
# NOTE: The full Multimodal (frames/audio) pipeline requires external infrastructure 
# (e.g., Ffmpeg, Cloud Storage, and a video processing service). For this environment, 
# the robust solution is to rely on Gemini's grounding/web-fetching capability via the URL 
# and use the more powerful 'pro' model for better inference from metadata.

# Imports for PDF Generation (Assuming ReportLab is installed)
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    PDF_ENABLED = True
except ImportError:
    logging.warning("ReportLab not installed. PDF generation will be mocked.")
    PDF_ENABLED = False


# --- Senior Dev Constants for Robustness ---
MAX_RETRIES = 3
TRANSCRIPT_FALLBACK_MARKER = "NO_TRANSCRIPT_FALLBACK" 
# -------------------------------------------

# Initialize logger
logger = logging.getLogger(__name__)

# --- Helper Functions ---

def extract_video_id(url):
    """
    Extracts the YouTube video ID from various URL formats.
    """
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    
    if "youtube.com/live/" in url:
        return url.split("/")[-1].split("?")[0]
    
    parsed_url = urlparse(url)
    if parsed_url.query:
        query_params = parse_qs(parsed_url.query)
        return query_params.get('v', [None])[0]
        
    return None

def fetch_transcript_robust(video_id):
    """
    Fetches the transcript with retries and robust language fallbacks.
    Returns: full_transcript string OR a special marker/prefix.
    """
    if not video_id:
        return TRANSCRIPT_FALLBACK_MARKER
    
    target_languages = ['en', 'en-US', 'en-GB'] 

    for attempt in range(MAX_RETRIES):
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript_obj = None
            
            try:
                transcript_obj = transcript_list.find_transcript(target_languages, auto_generate=True)
            except NoTranscriptFound:
                try:
                    available_codes = [t.language_code for t in transcript_list]
                    transcript_obj = transcript_list.find_transcript(available_codes, auto_generate=True)
                except NoTranscriptFound:
                    raise NoTranscriptFound("No transcript found in any language, manual or auto-generated.")

            transcript_data = transcript_obj.fetch()
            full_transcript = " ".join([item['text'] for item in transcript_data])
            
            if transcript_obj.language_code not in target_languages:
                return f"NON_ENGLISH_TRANSCRIPT:{transcript_obj.language_code}:{full_transcript}"

            return full_transcript # Success: return English transcript

        except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript, VideoUnavailable) as e:
            logger.warning(f"Transcript failure on attempt {attempt+1}/{MAX_RETRIES} for {video_id}. Error: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt) 
                continue
            
            return TRANSCRIPT_FALLBACK_MARKER
        
        except Exception as e:
            logger.error(f"Critical error during transcript fetch for {video_id}: {e}")
            return TRANSCRIPT_FALLBACK_MARKER

# --- PDF Generation Functions ---

def add_watermark(canvas, doc):
    """Draws the LearnFlow AI watermark on every page."""
    canvas.saveState()
    # Use a large, semi-transparent text for the watermark
    canvas.setFont('Helvetica-Bold', 60)
    canvas.setFillColor(colors.lightgrey, alpha=0.3)
    # Position the watermark diagonally across the center of the page
    canvas.translate(250, 400)
    canvas.rotate(45)
    canvas.drawString(0, 0, 'LearnFlow AI')
    canvas.restoreState()

def generate_pdf_report(video_id, quiz_data, user_answers, final_score, total_questions):
    """Generates the quiz report and certificate in a single PDF."""
    if not PDF_ENABLED:
        logger.error("PDF_ENABLED is False. Skipping PDF generation.")
        # Return a simple mock PDF (e.g., one page with the score) if ReportLab is not available
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.drawString(72, 800, f"MOCK Report - Score: {final_score}/{total_questions}")
        c.save()
        return buffer.getvalue()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            title=f"LearnFlow AI Report for {video_id}",
                            topMargin=50, bottomMargin=50)
    
    # Register the watermark function to be called on every page
    doc.build(generate_pdf_elements(video_id, quiz_data, user_answers, final_score, total_questions), onFirstPage=add_watermark, onLaterPages=add_watermark)
    
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

def generate_pdf_elements(video_id, quiz_data, user_answers, final_score, total_questions):
    """Creates the content elements for the PDF."""
    styles = getSampleStyleSheet()
    story = []

    # --- CERTIFICATE SECTION ---
    # Create a large box for the certificate effect
    story.append(Spacer(1, 120))
    story.append(Paragraph('<font size="24">CERTIFICATE OF COMPLETION</font>', styles['h1']))
    story.append(Spacer(1, 40))
    story.append(Paragraph(f'This certifies that a user has successfully completed the learning assessment for:', styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f'<font size="18" color="{colors.blue.name}">YouTube Video ID: {video_id}</font>', styles['h2']))
    story.append(Spacer(1, 24))
    
    # Display the score prominently
    score_color = colors.darkgreen if final_score > (total_questions / 2) else colors.red
    story.append(Paragraph(f'<font size="16"><b>Final Score: {final_score} / {total_questions}</b></font>', ParagraphStyle(name='ScoreStyle', fontName='Helvetica-Bold', fontSize=16, alignment=1, textColor=score_color)))
    story.append(Spacer(1, 80))
    
    story.append(Paragraph('Date Issued: {}'.format(time.strftime("%Y-%m-%d")), styles['Normal']))
    story.append(Spacer(1, 6))
    story.append(Paragraph('LearnFlow AI Assessment System', styles['Normal']))
    story.append(Spacer(1, 100))
    story.append(Paragraph('<pageBreak/>', styles['Normal']))

    # --- DETAILED REPORT SECTION ---
    story.append(Paragraph('<font size="16">Detailed Quiz Report</font>', styles['h1']))
    story.append(Spacer(1, 12))
    
    # Table data for the report
    report_data = [['#', 'Question', 'User Answer', 'Correct Answer', 'Result']]
    q_num = 1
    
    for q_index, q in enumerate(quiz_data):
        q_id = str(q_index)
        user_ans = user_answers.get(q_id, 'N/A')
        correct_ans = q.get('correct_answer', 'N/A')
        is_correct = 'CORRECT'
        
        # Re-run the scoring logic for display
        if q.get('type') == 'MCQ':
            try:
                # User answer is an index string. Check if it matches the correct answer index.
                if int(user_ans) != int(q.get('correctAnswerIndex', -1)):
                    is_correct = 'WRONG'
            except:
                is_correct = 'WRONG' # Invalid or missing user response

        elif q.get('type') == 'ShortAnswer':
            # Robust scoring check for short answers
            user_ans_normalized = user_ans.strip().lower()
            correct_ans_normalized = correct_ans.strip().lower()
            if user_ans_normalized != correct_ans_normalized:
                is_correct = 'WRONG'
            
        # Determine how to display the user answer for different types
        if q['type'] == 'MCQ':
            # For MCQ, the correct answer is the option text, not the index
            correct_option_index = q.get('correctAnswerIndex', -1)
            correct_ans_text = q['options'][correct_option_index] if correct_option_index >= 0 else 'N/A'
            user_ans_text = q['options'][int(user_ans)] if user_ans != 'N/A' and user_ans.isdigit() else user_ans
        else:
            # ShortAnswer
            correct_ans_text = correct_ans # The expected text answer
            user_ans_text = user_ans # The text input by the user

        # Use different colors for WRONG/CORRECT
        result_color = colors.darkgreen if is_correct == 'CORRECT' else colors.red
        result_text = Paragraph(f'<font color="{result_color.name}"><b>{is_correct}</b></font>', styles['Normal'])

        report_data.append([
            str(q_num),
            Paragraph(q['question'], styles['Normal']),
            Paragraph(str(user_ans_text), styles['Normal']),
            Paragraph(str(correct_ans_text), styles['Normal']),
            result_text
        ])
        q_num += 1

    # Create the table with column widths
    table = Table(report_data, colWidths=[30, 180, 100, 100, 60])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a73e8')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('LEFTPADDING', (1, 1), (-1, -1), 6),
        ('RIGHTPADDING', (1, 1), (-1, -1), 6),
    ]))

    story.append(table)
    
    return story


# --- API Views ---

# You must set your API key as an environment variable in your production environment
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

@csrf_exempt # Note: This is acceptable for an API-focused view, but full protection is better.
def analyze_video_api(request):
    """
    Handles POST requests to analyze a video URL using Gemini.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed.'}, status=405)

    try:
        data = json.loads(request.body)
        video_url = data.get('video_url')
        video_id = data.get('video_id')
        
        if not video_url or not video_id:
            return JsonResponse({'status': 'error', 'message': 'Missing video URL or ID.'}, status=400)
        
        if not GEMINI_API_KEY:
            logger.error("GEMINI_API_KEY is not set.")
            return JsonResponse({'status': 'error', 'message': 'API key not configured on the server.'}, status=503)

        # 1. Fetch Transcript (Robustly)
        transcript = fetch_transcript_robust(video_id)
        
        # 2. Prepare the Prompt for Gemini
        # Prioritize the transcript if available, otherwise rely on the URL's contents.
        transcript_content = ""
        if transcript.startswith("NON_ENGLISH_TRANSCRIPT:"):
            lang_code, actual_transcript = transcript.split(":", 2)[1:]
            transcript_content = f"The following is a non-English transcript (Language: {lang_code}). Use it to help generate the analysis:\n{actual_transcript}"
        elif transcript == TRANSCRIPT_FALLBACK_MARKER:
            transcript_content = "No machine or auto-generated transcript could be reliably fetched. Rely on the video URL and its title/description for the summary."
        else:
            transcript_content = f"Use the following transcript to generate a highly accurate summary and quiz:\n{transcript}"

        prompt = f"""
        You are a video analysis AI for an educational platform. Your task is to analyze the provided YouTube video URL and its content.

        **Video URL:** {video_url}
        **Content/Transcript Status:** {transcript_content}
        
        Based on this information, generate a comprehensive analysis in a single JSON block. The JSON must have the following two top-level keys:

        1.  `summary`: A detailed, markdown-formatted summary of the video's main points, key concepts, and conclusion. Use headings, lists, and bold text.
        2.  `quiz_questions`: An array of at least 15 high-quality, educationally relevant questions. Ensure a mix of **Multiple Choice Questions (MCQ)** and **Short Answer** questions.

        **JSON Format Requirements for Questions:**
        - **MCQ Questions:** Must have `type: "MCQ"`, a `question`, an `options` array (with 4 choices), a `correctAnswerIndex` (integer 0-3), and a `correct_answer` (string, which is the text of the correct option).
        - **Short Answer Questions:** Must have `type: "ShortAnswer"`, a `question`, and a concise, single-sentence `correct_answer` (string). Do not provide an options array.

        Example Structure:
        ```json
        {{
            "summary": "...",
            "quiz_questions": [
                {
                    "type": "MCQ",
                    "question": "...",
                    "options": ["A", "B", "C", "D"],
                    "correctAnswerIndex": 0,
                    "correct_answer": "A"
                },
                {{
                    "type": "ShortAnswer",
                    "question": "...",
                    "correct_answer": "..."
                }}
            ]
        }}
        ```
        Ensure the JSON is valid and complete, and do not include any text outside of the JSON block.
        """
        
        # 3. Call Gemini
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        config = types.GenerateContentConfig(
            # Enable the model to fetch and ground its response on the web, using the URL.
            # This is crucial for videos where the transcript is missing or poor.
            tools=[{"google_search": {}}], 
            temperature=0.3, # Low temperature for factual, consistent quiz generation
        )

        response = client.models.generate_content(
            model='gemini-2.5-pro', # Use a powerful model for complex reasoning and structure generation
            contents=prompt,
            config=config,
        )

        # 4. Parse Response
        # The model is instructed to return a pure JSON block.
        try:
            # Attempt to find and parse the JSON block from the response text
            json_start = response.text.find('{')
            json_end = response.text.rfind('}')
            if json_start == -1 or json_end == -1:
                raise ValueError("Could not find a valid JSON block in model response.")

            json_text = response.text[json_start : json_end + 1]
            analysis_data = json.loads(json_text)
            
            # Add the transcript back into the response for the frontend's Transcript tab
            analysis_data['transcript'] = transcript
            
            return JsonResponse(analysis_data)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI response: {e}. Raw response: {response.text[:500]}...")
            return JsonResponse({'status': 'error', 'message': 'AI response was malformed or incomplete. Please try again.'}, status=500)
        
    except APIError as e:
        logger.error(f"Gemini API Error: {e}")
        return JsonResponse({'status': 'error', 'message': f'AI service failed to generate content: {str(e)}'}, status=500)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON in request body.'}, status=400)
    except Exception as e:
        logger.exception(f"Unexpected error in analyze_video_api: {e}")
        return JsonResponse({'status': 'error', 'message': f'A critical server error occurred: {e}'}, status=500)


@csrf_exempt # Note: This is acceptable for an API-focused view, but full protection is better.
def submit_quiz_api(request):
    """
    Handles POST requests to score the quiz and generate a PDF report.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed.'}, status=405)
        
    if not PDF_ENABLED:
        return JsonResponse({'status': 'error', 'message': 'ReportLab is not installed on the server. PDF generation is disabled.'}, status=503)

    try:
        data = json.loads(request.body)
        video_id = data.get('video_id')
        quiz_data = data.get('quiz_data', [])
        user_answers = data.get('user_answers', {})
        
        if not video_id or not quiz_data:
            return JsonResponse({"status": "error", "message": "Missing video ID or quiz data."}, status=400)

        final_score = 0
        total_questions = len(quiz_data)

        # 1. Score the Quiz
        for q_index, q in enumerate(quiz_data):
            q_id = str(q_index)
            user_ans = user_answers.get(q_id)
            is_correct = False
            
            # Skip if user didn't answer (should be prevented by frontend, but server must be defensive)
            if user_ans is None:
                continue

            # Standardized scoring for MCQ
            if q.get('type') == 'MCQ':
                correct_ans_index = q.get('correctAnswerIndex')
                try:
                    # User answer is the index string from the radio button value
                    if int(user_ans) == int(correct_ans_index):
                        is_correct = True
                except:
                    pass # User response was invalid or missing

            elif q.get('type') == 'ShortAnswer':
                correct_ans = q.get('correct_answer')
                
                # --- SENIOR DEV ROBUSTNESS FIX ---
                # Normalize both answers for case-insensitivity and leading/trailing whitespace
                user_ans_normalized = str(user_ans).strip().lower()
                correct_ans_normalized = str(correct_ans).strip().lower()

                if user_ans_normalized == correct_ans_normalized:
                    is_correct = True
                # ---------------------------------
            
            if is_correct:
                final_score += 1
        
        # 2. Generate PDF Report
        pdf_data = generate_pdf_report(video_id, quiz_data, user_answers, final_score, total_questions)

        # 3. Return the PDF file as a response
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="LearnFlow_AI_Report_{video_id}.pdf"'
        
        # Add the score to the response header/body so the frontend can display it before/after download
        response['X-Quiz-Score'] = f'{final_score}/{total_questions}'
        
        return response

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON format in quiz submission."}, status=400)
    except Exception as e:
        logger.exception(f"Error during quiz submission or PDF generation: {e}")
        return JsonResponse({"status": "error", "message": f"A server error occurred during scoring/PDF generation: {e}"}, status=500)


# --- Static Pages Views (Original content) ---
def privacy_policy(request): return render(request, 'privacy.html')
def terms_conditions(request): return render(request, 'terms.html')
def about_us(request): return render(request, 'about.html')
def contact_us(request): return render(request, 'contact.html')
def sitemap_page(request): return render(request, 'sitemap-page.html')
def learnflow_overview(request): return render(request, 'learnflow_overview.html')

def learnflow_video_analysis(request):
    """The main view for the video analysis page."""
    # This view can be used to pass initial context, like a pre-selected video ID.
    context = {}
    return render(request, 'learnflow.html', context)
    
def video_analysis_view(request, video_id):
    """
    View to handle direct links to a video analysis page, pre-populating the URL.
    """
    context = {'pre_selected_video_id': video_id}
    return render(request, 'learnflow.html', context)