import os
import logging
import time 
import json 
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlparse, parse_qs
from io import BytesIO 

# Imports for Transcript Fetching
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

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
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
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
    """Extracts the YouTube video ID from various URL formats."""
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
                # Prioritize English/Auto-generated English
                transcript_obj = transcript_list.find_transcript(target_languages, auto_generate=True)
            except NoTranscriptFound:
                try:
                    # Fallback to any available language
                    available_codes = [t.language_code for t in transcript_list]
                    transcript_obj = transcript_list.find_transcript(available_codes, auto_generate=True)
                except NoTranscriptFound:
                    raise NoTranscriptFound("No transcript found in any language, manual or auto-generated.")

            transcript_data = transcript_obj.fetch()
            full_transcript = " ".join([item['text'] for item in transcript_data])
            
            if transcript_obj.language_code not in target_languages:
                # Return prefix for non-English transcript
                return f"NON_ENGLISH_TRANSCRIPT:{transcript_obj.language_code}:{full_transcript}"

            return full_transcript # Success: return English transcript

        except Exception as e:
            logger.warning(f"Transcript failure on attempt {attempt+1}/{MAX_RETRIES} for {video_id}. Error: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt) 
                continue
            
            return TRANSCRIPT_FALLBACK_MARKER

# --- PDF Generation Functions (Implementation omitted for brevity, assuming they are correct) ---

def add_watermark(canvas, doc):
    """Draws the LearnFlow AI watermark on every page."""
    canvas.saveState()
    canvas.setFont('Helvetica-Bold', 60)
    canvas.setFillColor(colors.lightgrey, alpha=0.3)
    canvas.translate(250, 400)
    canvas.rotate(45)
    canvas.drawString(0, 0, 'LearnFlow AI')
    canvas.restoreState()

def generate_pdf_report(video_id, quiz_data, user_answers, final_score, total_questions):
    """Generates the quiz report and certificate in a single PDF."""
    if not PDF_ENABLED:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.drawString(72, 800, f"MOCK Report - Score: {final_score}/{total_questions}")
        c.save()
        return buffer.getvalue()

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            title=f"LearnFlow AI Report for {video_id}",
                            topMargin=50, bottomMargin=50)
    
    doc.build(generate_pdf_elements(video_id, quiz_data, user_answers, final_score, total_questions), onFirstPage=add_watermark, onLaterPages=add_watermark)
    
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

def generate_pdf_elements(video_id, quiz_data, user_answers, final_score, total_questions):
    """Creates the content elements for the PDF."""
    styles = getSampleStyleSheet()
    story = []

    # Certificate Section
    story.append(Spacer(1, 120))
    story.append(Paragraph('<font size="24">CERTIFICATE OF COMPLETION</font>', styles['h1']))
    story.append(Spacer(1, 40))
    story.append(Paragraph(f'This certifies that a user has successfully completed the learning assessment for:', styles['Normal']))
    story.append(Spacer(1, 12))
    story.append(Paragraph(f'<font size="18" color="{colors.blue.name}">YouTube Video ID: {video_id}</font>', styles['h2']))
    story.append(Spacer(1, 24))
    
    score_color = colors.darkgreen if final_score > (total_questions / 2) else colors.red
    score_style = ParagraphStyle(name='ScoreStyle', fontName='Helvetica-Bold', fontSize=16, alignment=1, textColor=score_color)
    story.append(Paragraph(f'<font size="16"><b>Final Score: {final_score} / {total_questions}</b></font>', score_style))
    story.append(Spacer(1, 80))
    
    story.append(Paragraph('Date Issued: {}'.format(time.strftime("%Y-%m-%d")), styles['Normal']))
    story.append(Spacer(1, 100))
    story.append(Paragraph('<pageBreak/>', styles['Normal']))

    # Detailed Report Section
    story.append(Paragraph('<font size="16">Detailed Quiz Report</font>', styles['h1']))
    story.append(Spacer(1, 12))
    
    report_data = [['#', 'Question', 'User Answer', 'Correct Answer', 'Result']]
    q_num = 1
    
    for q_index, q in enumerate(quiz_data):
        q_id = str(q_index)
        user_ans = user_answers.get(q_id, 'N/A')
        correct_ans = q.get('correct_answer', 'N/A')
        is_correct = 'WRONG' 
        correct_ans_text = str(correct_ans)
        user_ans_text = str(user_ans)
        
        if q.get('type') == 'MCQ':
            correct_option_index = q.get('correctAnswerIndex', -1)
            correct_ans_text = q['options'][correct_option_index] if correct_option_index >= 0 and correct_option_index < len(q['options']) else 'N/A'
            
            try:
                if int(user_ans) == int(correct_option_index):
                    is_correct = 'CORRECT'
            except:
                pass 

            user_ans_text = q['options'][int(user_ans)] if user_ans.isdigit() and int(user_ans) < len(q['options']) else 'N/A'

        elif q.get('type') == 'ShortAnswer':
            user_ans_normalized = str(user_ans).strip().lower()
            correct_ans_normalized = str(correct_ans).strip().lower()
            
            if user_ans_normalized == correct_ans_normalized and user_ans_normalized != '':
                is_correct = 'CORRECT'
            
            user_ans_text = str(user_ans) 
            
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

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

@csrf_exempt
def analyze_video_api(request):
    """Handles POST requests to analyze a video URL using Gemini, optimized for latency."""
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
        transcript_content = ""
        transcript_instruction = ""
        
        if transcript.startswith("NON_ENGLISH_TRANSCRIPT:"):
            lang_code, actual_transcript = transcript.split(":", 2)[1:]
            transcript_content = f"The following is a non-English transcript (Language: {lang_code}). Use it to help generate the analysis:\n{actual_transcript}"
            transcript_instruction = "The transcript provided is non-English, but use it as a primary source for the analysis."
            
        elif transcript == TRANSCRIPT_FALLBACK_MARKER:
            transcript_content = "No machine or auto-generated transcript could be reliably fetched. The model must rely solely on the video URL, title, and description for the analysis."
            transcript_instruction = """
            **CRITICAL ACTION REQUIRED (Memory Optimized):** Since no transcript was retrieved, you MUST rely on the video URL, title, and description.
            
            **To ensure high-quality output, as a primary step, analyze the video's content and generate a highly detailed, chronological analysis of the narration/dialogue.**
            
            **Include this content under a new top-level JSON key named 'gemini_generated_analysis' (do NOT call it 'transcript', as it is an analysis, not a verbatim text).**
            
            The length of 'gemini_generated_analysis' must be detailed but **concise**—NOT a full, verbatim transcript.
            
            Then, use this generated 'gemini_generated_analysis' content to create the 'summary' and 'quiz_questions'.
            """
            
        else:
            transcript_content = f"Use the following transcript to generate a highly accurate summary and quiz:\n{transcript}"
            transcript_instruction = "The transcript is provided below. Use it as the primary source for the analysis."

        prompt = f"""
        You are a video analysis AI for an educational platform. Your task is to analyze the provided YouTube video URL and its content.

        **Video URL:** {video_url}
        **Transcript Status/Instructions:** {transcript_instruction}
        
        **Transcript Content:**
        {transcript_content}
        
        Based on this information, generate a comprehensive analysis in a single JSON block. The JSON must have the following primary top-level keys:

        1.  `summary`: A detailed, markdown-formatted summary of the video's main points, key concepts, and conclusion. Use headings, lists, and bold text.
        2.  `quiz_questions`: An array of at least 15 high-quality, educationally relevant questions. Ensure a mix of **Multiple Choice Questions (MCQ)** and **Short Answer** questions, following the strict format below.

        **If you were instructed to generate an analysis because the transcript was missing, you MUST include a third key:**
        3. `gemini_generated_analysis`: A long string containing the detailed chronological analysis (NOT a full transcript).

        **JSON Format Requirements for Questions:**
        - **MCQ Questions:** Must have `type: "MCQ"`, a `question`, an `options` array (with 4 choices), a `correctAnswerIndex` (integer 0-3), and a `correct_answer` (string, which is the text of the correct option).
        - **Short Answer Questions:** Must have `type: "ShortAnswer"`, a `question`, and a concise, single-sentence `correct_answer` (string). Do not provide an options array.

        Example Structure:
        ```json
        {{
            "summary": "...",
            "quiz_questions": [
                {{
                    "type": "MCQ",
                    // ...
                }},
                {{
                    "type": "ShortAnswer",
                    // ...
                }}
            ]
        }}
        ```
        Ensure the JSON is valid and complete, and do not include any text outside of the JSON block.
        """
        
        # 3. Call Gemini (Using Flash for speed)
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        config = types.GenerateContentConfig(
            tools=[{"google_search": {}}], 
            temperature=0.3,
        )

        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=config,
        )

        # 4. Parse Response
        try:
            json_start = response.text.find('{')
            json_end = response.text.rfind('}')
            if json_start == -1 or json_end == -1:
                raise ValueError("Could not find a valid JSON block in model response.")

            json_text = response.text[json_start : json_end + 1]
            analysis_data = json.loads(json_text)
            
            # Add the original transcript/marker back for frontend display
            analysis_data['transcript'] = transcript
            
            return JsonResponse(analysis_data)
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse AI response: {e}. Raw response: {response.text[:500]}...")
            return JsonResponse({'status': 'error', 'message': 'AI response was malformed or incomplete. Please try again. (Server JSON error)'}, status=500)
        
    except APIError as e:
        logger.error(f"Gemini API Error: {e}")
        return JsonResponse({'status': 'error', 'message': f'AI service failed. This often means the video is too long for a single request, or the Gemini API timed out: {str(e)}'}, status=500)
    except Exception as e:
        logger.exception(f"Unexpected error in analyze_video_api: {e}")
        return JsonResponse({'status': 'error', 'message': 'A critical server error occurred: ' + str(e)}, status=500)


@csrf_exempt
def submit_quiz_api(request):
    """Handles POST requests to score the quiz and generate a PDF report."""
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
            
            if user_ans is None or user_ans == '':
                continue

            if q.get('type') == 'MCQ':
                correct_ans_index = q.get('correctAnswerIndex')
                try:
                    if int(user_ans) == int(correct_ans_index):
                        is_correct = True
                except:
                    pass 

            elif q.get('type') == 'ShortAnswer':
                correct_ans = q.get('correct_answer')
                
                # Robust comparison: case-insensitive and whitespace-trimmed
                user_ans_normalized = str(user_ans).strip().lower()
                correct_ans_normalized = str(correct_ans).strip().lower()

                if user_ans_normalized == correct_ans_normalized:
                    is_correct = True
            
            if is_correct:
                final_score += 1
        
        # 2. Generate PDF Report
        pdf_data = generate_pdf_report(video_id, quiz_data, user_answers, final_score, total_questions)

        # 3. Return the PDF file
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="LearnFlow_AI_Report_{video_id}.pdf"'
        
        # Pass the score back via a custom header
        response['X-Quiz-Score'] = f'{final_score}/{total_questions}'
        
        return response

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
    """View to handle direct links to a video analysis page, pre-populating the URL."""
    context = {'pre_selected_video_id': video_id}
    return render(request, 'learnflow.html', context)