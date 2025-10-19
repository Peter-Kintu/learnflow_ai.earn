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
    # ... (Keep existing fetch_transcript_robust implementation as it was robustly updated in the last step)
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

# --- PDF Generation Functions (New) ---

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
        is_correct = 'CORRECT' if user_ans == correct_ans else 'WRONG'
        
        # Determine how to display the user answer for different types
        if q['type'] == 'MCQ':
            # For MCQ, the correct answer is the option text, not the index
            correct_option_index = q.get('correctAnswerIndex', -1)
            correct_ans_text = q['options'][correct_option_index] if correct_option_index >= 0 else 'N/A'
            user_ans_text = q['options'][int(user_ans)] if user_ans != 'N/A' and user_ans.isdigit() else user_ans
        else: # ShortAnswer
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
    ]))
    story.append(table)
    
    return story

# --- Main Application Views ---

def learnflow_video_analysis(request):
    """Renders the main template."""
    return render(request, 'learnflow.html', {
        'api_key': os.getenv('GEMINI_API_KEY') 
    })

def learnflow_overview(request):
    """Renders the overview page."""
    return render(request, 'learnflow_overview.html') 

# --- Static Pages Views (Omitted for brevity) ---
def privacy_policy(request): return render(request, 'privacy.html')
def terms_conditions(request): return render(request, 'terms.html')
def about_us(request): return render(request, 'about.html')
def contact_us(request): return render(request, 'contact.html')
def sitemap_page(request): return render(request, 'sitemap.html')
def video_analysis_view(request, video_id): return render(request, 'learnflow.html', {'pre_selected_video_id': video_id})


# --- API View: Analysis & Quiz Generation ---

@csrf_exempt
def analyze_video_api(request): 
    """
    API endpoint to fetch transcript and generate AI summary and a large, mixed quiz.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Invalid request method. Must use POST."}, status=400)

    # ... (API Key and URL extraction setup remains the same)
    video_id = None
    video_link = None
        
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables.")
        return JsonResponse({"status": "error", "message": "AI service not configured."}, status=500)
    
    try:
        data = json.loads(request.body)
        video_link = data.get('video_link', '').strip() 
        
        if not video_link:
            return JsonResponse({"status": "error", "message": "No YouTube link provided."}, status=400)
        
        video_id = extract_video_id(video_link)
        if not video_id:
            return JsonResponse({"status": "error", "message": "Could not extract a valid YouTube video ID."}, status=400)
        
        logger.info(f"Analysis request received for video ID: {video_id}")
        
        # --- 2. Transcript Fetch Attempt ---
        transcript_text_raw = fetch_transcript_robust(video_id)

        transcript_to_process = ""
        prompt_instruction = ""
        transcript_found = (transcript_text_raw != TRANSCRIPT_FALLBACK_MARKER)

        if transcript_text_raw.startswith("NON_ENGLISH_TRANSCRIPT:"):
            _, lang_code, content = transcript_text_raw.split(":", 2)
            transcript_to_process = content
            prompt_instruction = (
                f"The following video content is in **{lang_code}**. You MUST first translate the content to English. "
                "Then, proceed with the summarization and question generation based on the English translation."
            )
        elif not transcript_found:
            transcript_to_process = f"Original Video URL: {video_link}" 
            prompt_instruction = (
                "The automatic transcript for this video could not be retrieved. "
                "You MUST use your general knowledge, grounding capabilities, or the video URL provided in the content section to determine the video's title, subject, and main content. "
                "Generate the requested SUMMARY and QUESTIONS based on the video's known topic and purpose. "
                "The summary MUST begin with the sentence: 'Note: The analysis below is based on the video's title and public information, as the transcript was unavailable.'"
            )
        else:
            transcript_to_process = transcript_text_raw
            prompt_instruction = "Based on the following video content, perform the tasks."

        # --- 3. AI Summarization and Quiz Generation ---
        client = genai.Client(api_key=api_key)
        
        # CRITICAL UPDATE: New prompt for 20+ mixed questions
        prompt = (
            f"{prompt_instruction}\n\n"
            "Perform two tasks:\n"
            "1. **SUMMARY (3-5 Sentences):** Summarize the main topics and key takeaways in a concise, informative paragraph. The summary MUST be 3-5 sentences long.\n"
            "2. **QUESTIONS (20+ Items):** Generate a minimum of 20 challenging questions that test comprehension. The questions MUST be a mix of two types:\n"
            "   a. **Multiple Choice (MCQ):** Each must have 4 options.\n"
            "   b. **Short Answer (SA):** The answer must be a single word or short phrase that must be typed by the user.\n\n"
            "Format your response strictly as a JSON object with two top-level keys: 'summary' (string) and 'questions' (list of question objects).\n\n"
            f"Video Context for Grounding: {video_link}\n\n" 
            f"Video Content (Transcript/Marker):\n\n{transcript_to_process}"
        )

        # CRITICAL UPDATE: New Schema to support multiple question types
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "summary": {"type": "string"},
                "questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "type": {"type": "string", "enum": ["MCQ", "ShortAnswer"]}, # New: type field
                            "options": {"type": "array", "items": {"type": "string"}, "description": "Required only for MCQ type."},
                            "correct_answer": {"type": "string"} # The required answer (text for SA, or the option text for MCQ)
                        },
                        "required": ["question", "type", "correct_answer"]
                    }
                }
            },
            required=["summary", "questions"]
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            )
        )

        # 4. Process and Return the successful response
        ai_data = json.loads(response.text)
        
        # Post-process questions to calculate the internal correct index for MCQs
        processed_questions = []
        for q in ai_data.get("questions", []):
            if q.get('type') == 'MCQ':
                correct_index = -1
                correct_ans_str = q.get("correct_answer", "").strip()
                options = q.get("options", [])
                
                # Find the index of the correct answer string within the options array
                try:
                    correct_index = options.index(correct_ans_str)
                except ValueError:
                    logger.warning(f"AI answer string '{correct_ans_str}' not found in options for {video_id}.")
                
                # Store the index for frontend use, but keep 'correct_answer' for scoring API
                q['correctAnswerIndex'] = correct_index
            
            processed_questions.append(q)

        response_data = {
            "status": "success",
            "summary": ai_data.get("summary", "Summary could not be generated."),
            "questions": processed_questions, # Renamed from 'quiz' to 'questions'
            "transcript_status": "FOUND" if transcript_found else "NOT_FOUND",
            "video_id": video_id,
            "transcript_text": transcript_text_raw if transcript_found else "Transcript Unavailable. Analysis based on public topic." 
        }
        return JsonResponse(response_data)

    except APIError as e:
        logger.exception(f"Gemini API Error for {video_id}: {str(e)}")
        return JsonResponse({"status": "error", "message": f"AI service failed (Gemini API Error)."}, status=503)

    except json.JSONDecodeError:
        logger.exception(f"AI response was not valid JSON for {video_id}.")
        return JsonResponse({"status": "error", "message": "AI service returned an invalid response format."}, status=500)

    except Exception as e:
        logger.exception(f"A critical, unhandled error occurred during fetch/AI processing for {video_id}.")
        return JsonResponse({"status": "error", "message": f"A critical server error occurred during processing: {e}"}, status=500)

# --- NEW API View: Quiz Submission and PDF Report Generation ---

@csrf_exempt
def submit_quiz_api(request):
    """
    Receives user answers, calculates score, and generates the PDF report/certificate.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Invalid request method. Must use POST."}, status=400)

    if not PDF_ENABLED:
        return JsonResponse({"status": "error", "message": "PDF generation library (ReportLab) is not installed on the server."}, status=501)

    try:
        data = json.loads(request.body)
        user_answers = data.get('user_answers', {}) # {q_index: user_response, ...}
        quiz_data = data.get('quiz_data', []) # The original questions with correct answers
        video_id = data.get('video_id', 'Unknown Video')

        final_score = 0
        total_questions = len(quiz_data)
        
        # 1. Score the Quiz
        for q_index, q in enumerate(quiz_data):
            q_id = str(q_index)
            user_ans = user_answers.get(q_id, '').strip().lower()
            correct_ans = q.get('correct_answer', '').strip().lower()
            q['correct_answer'] = correct_ans # Normalize the stored answer (important for report)

            is_correct = False
            
            if q.get('type') == 'MCQ':
                # For MCQ, the user answer is the INDEX (0, 1, 2, 3) selected by the radio button
                # We compare the user-selected option TEXT (extracted from options using the index) to the correct_answer text.
                try:
                    user_option_index = int(user_ans)
                    if user_option_index >= 0 and user_option_index < len(q.get('options', [])):
                        user_ans_text = q['options'][user_option_index].strip().lower()
                        if user_ans_text == correct_ans:
                            is_correct = True
                except:
                    pass # User response was invalid or missing

            elif q.get('type') == 'ShortAnswer':
                # For ShortAnswer, compare the user-typed text directly
                if user_ans == correct_ans:
                    is_correct = True
            
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
# ... (kept as before)