import os
import logging
import time 
import json 
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
# REMOVED: from django.views.decorators.csrf import csrf_exempt 
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
    # Senior Dev fix: Ensure all platypus elements are imported
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    PDF_ENABLED = True
except ImportError:
    # This warning indicates ReportLab is missing, but should not stop the web app.
    logging.warning("ReportLab not installed. PDF generation will be mocked.")
    PDF_ENABLED = False


# --- Senior Dev Constants for Robustness ---
MAX_RETRIES = 3
TRANSCRIPT_FALLBACK_MARKER = "NO_TRANSCRIPT_FALLBACK" 
# -------------------------------------------

# Initialize logger
logger = logging.getLogger(__name__)

# --- Helper Functions (Defined outside views for reusability) ---

def extract_video_id(url):
    """Extracts the YouTube video ID from various URL formats."""
    if not url:
        return None
    try:
        url_data = urlparse(url)
        # Check for standard watch URL
        if url_data.netloc in ['www.youtube.com', 'youtube.com'] and url_data.path == '/watch':
            query = parse_qs(url_data.query)
            return query.get('v', [None])[0]
        # Check for shortened youtu.be URL
        elif url_data.netloc in ['youtu.be']:
            return url_data.path[1:] # Strip the leading '/'
        return None
    except Exception:
        return None


def get_youtube_transcript(video_id):
    """Fetches the transcript using the YouTube Transcript API, with fallback handling."""
    if not video_id:
        return TRANSCRIPT_FALLBACK_MARKER
        
    for attempt in range(MAX_RETRIES):
        try:
            # Try to get the English transcript first
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            # Prioritize English if available
            try:
                transcript = transcript_list.find_transcript(['en'])
            except NoTranscriptFound:
                # Fallback to a single auto-generated transcript if English is missing
                try:
                    transcript = transcript_list.find_transcript(['en', 'es', 'fr', 'de'])
                except NoTranscriptFound:
                    # Fallback to the first available auto-generated transcript (it might be in any language)
                    transcript = next((t for t in transcript_list if t.is_generated), None)
            
            if transcript:
                # If non-English is forced, note the language
                if not transcript.language_code.startswith('en') and transcript.language_code != 'en-GB':
                    logger.info(f"Using non-English transcript ({transcript.language_code}) for video ID: {video_id}")
                    # Fetch the actual non-English transcript
                    full_transcript = " ".join([item['text'] for item in transcript.fetch()])
                    return f"NON_ENGLISH_TRANSCRIPT:{transcript.language_code}:{full_transcript}"
                
                # Fetch and format the transcript
                full_transcript = " ".join([item['text'] for item in transcript.fetch()])
                return full_transcript
            
            # If no transcript found (NoTranscriptFound should have been caught, but as a final check)
            return TRANSCRIPT_FALLBACK_MARKER
            
        except TranscriptsDisabled:
            logger.warning(f"Transcripts disabled for video ID: {video_id}")
            return TRANSCRIPT_FALLBACK_MARKER
        except (NoTranscriptFound, CouldNotRetrieveTranscript, VideoUnavailable):
            # This is the most common failure: no transcript at all or API issue
            logger.warning(f"No transcript found for video ID: {video_id}")
            return TRANSCRIPT_FALLBACK_MARKER
        except Exception as e:
            logger.error(f"Attempt {attempt + 1}: General transcript error for {video_id}: {e}")
            time.sleep(1 * (attempt + 1)) # Backoff
            if attempt == MAX_RETRIES - 1:
                return TRANSCRIPT_FALLBACK_MARKER
        
    return TRANSCRIPT_FALLBACK_MARKER # Should be unreachable if logic is correct


def generate_gemini_analysis(video_url, transcript, video_id):
    """
    Calls the Gemini API to analyze the video and generate a summary and quiz.
    It uses the URL for grounding/web context and the transcript for detailed content.
    """
    try:
        # Senior Dev Check: Ensure API Key is available before proceeding.
        if not os.getenv("GEMINI_API_KEY"):
            logger.error("GEMINI_API_KEY environment variable not set. Aborting AI generation.")
            return {"error": "AI service not configured.", "details": "GEMINI_API_KEY is missing from environment variables."}

        # Initialize Gemini Client (assumes API key is in environment variables)
        # Note: In a production environment, the client should ideally be initialized once globally.
        client = genai.Client()
        model_name = 'gemini-2.5-pro' 
        
        # --- Prompt Engineering ---
        # If the transcript is missing, inform the model it must use web context (video URL)
        display_transcript = transcript
        if transcript == TRANSCRIPT_FALLBACK_MARKER or transcript.startswith("NON_ENGLISH_TRANSCRIPT:"):
             # For the prompt, provide a truncated version or specific instruction
             display_transcript = (
                 f"**NOTE:** The direct transcript was unavailable or non-English ({transcript.split(':')[1] if transcript.startswith('NON_ENGLISH_TRANSCRIPT:') else 'MISSING'}). "
                 "Rely primarily on the source video URL and its title/description for context. "
                 "Generate the summary and quiz based on expected video content. "
                 "For the `gemini_generated_analysis` field, include a note explaining that the analysis was performed without a direct English transcript."
             )


        prompt = f"""
        You are an AI educational assistant. Analyze the following content and instructions:
        
        **Source Video URL:** {video_url}
        
        **Available Text Content (Transcript):**
        {display_transcript}
        
        ---
        
        **TASK 1: Generate a Comprehensive Summary**
        Generate a detailed, well-structured summary of the video content, optimized for learning. 
        - Use clear headings and bullet points (Markdown format).
        - Focus on key concepts, definitions, and main takeaways.
        
        **TASK 2: Create a 5-Question Educational Quiz (JSON Format)**
        Create 5 unique questions based on the video content.
        - **Format:** The quiz MUST be returned as a single JSON array named `quiz_questions`.
        - **Types:** Include 3 Multiple-Choice Questions (MCQ) and 2 Short-Answer Questions.
        
        **JSON Structure Requirements:**
        ```json
        [
          {{
            "question": "...",
            "type": "MCQ", // or "ShortAnswer"
            "options": ["A", "B", "C", "D"], // Only for MCQ
            "correct_answer": "...", // Index (0-3) for MCQ, or short answer text for ShortAnswer
            "explanation": "..." 
          }},
          // ... 4 more questions
        ]
        ```
        
        **If the transcript is missing or non-English, rely on the video URL and title/description context for the summary and quiz, and use the 'gemini_generated_analysis' field for the transcript section.**
        
        ---
        
        **OUTPUT FORMAT:**
        The output must be a single JSON object with two fields:
        1.  `summary`: [String containing the Markdown summary]
        2.  `quiz_questions`: [JSON Array of 5 quiz questions]
        3.  `gemini_generated_analysis`: [String containing a brief note/analysis if the transcript was unavailable. Only required if the transcript was unavailable or non-English.]
        """
        
        # Use an appropriate configuration for structured output
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema={
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "quiz_questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "type": {"type": "string", "enum": ["MCQ", "ShortAnswer"]},
                                "options": {"type": "array", "items": {"type": "string"}},
                                "correct_answer": {"type": "string"},
                                "explanation": {"type": "string"}
                            },
                            "required": ["question", "type", "correct_answer", "explanation"]
                        }
                    },
                    "gemini_generated_analysis": {"type": "string"}
                },
                "required": ["summary", "quiz_questions"]
            }
        )
        
        # Call the Gemini API
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config,
        )

        # Parse the JSON response text
        response_data = json.loads(response.text)
        
        return {
            "summary": response_data.get("summary", "Analysis failed to generate a summary."),
            "quiz_questions": response_data.get("quiz_questions", []),
            "gemini_generated_analysis": response_data.get("gemini_generated_analysis", None)
        }

    except APIError as e:
        logger.error(f"Gemini API Error: {e}")
        return {"error": "AI service failed to generate content.", "details": str(e)}
    except json.JSONDecodeError as e:
        # Senior Dev: Log the raw response if possible to debug why JSON failed
        raw_response = response.text if 'response' in locals() else 'N/A'
        logger.error(f"JSON parsing error from Gemini: {e}. Raw response: {raw_response}")
        return {"error": "AI service returned an unparsable response.", "details": str(e)}
    except Exception as e:
        logger.error(f"General error during Gemini generation: {e}")
        return {"error": f"An unexpected error occurred during AI processing: {e}", "details": str(e)}


def generate_pdf_report(video_id, quiz_data, user_answers, final_score, total_questions):
    """Mocks PDF generation if ReportLab is missing, otherwise generates the PDF report."""
    
    if not PDF_ENABLED:
        logger.warning("PDF generation mocked. Returning dummy data.")
        # Return a simple dummy PDF in a BytesIO object
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=letter)
        c.drawString(72, 800, "PDF Generation Disabled (ReportLab not installed).")
        c.drawString(72, 780, f"Quiz Score: {final_score}/{total_questions}")
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    # --- Actual ReportLab PDF Generation Logic ---
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, 
                            rightMargin=72, leftMargin=72,
                            topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    
    Story = []
    
    # Title
    Story.append(Paragraph(f"LearnFlow AI Video Analysis Report", styles['Title']))
    Story.append(Paragraph(f"Video ID: {video_id}", styles['Normal']))
    Story.append(Spacer(1, 12))
    
    # Score Summary
    Story.append(Paragraph(f"<b>Quiz Results:</b> {final_score} out of {total_questions} correct", styles['h2']))
    Story.append(Spacer(1, 12))

    # Quiz Questions Review
    for i, q in enumerate(quiz_data):
        q_num = i + 1
        
        # Question Text
        Story.append(Paragraph(f"<b>Question {q_num}. ({q['type']}):</b> {q['question']}", styles['Normal']))
        
        user_ans = user_answers.get(str(i), '')
        correct_ans = str(q['correct_answer'])
        is_correct = False
        
        if q['type'] == 'MCQ':
            try:
                # User and correct answer are expected to be string indices ("0", "1", etc.)
                user_option_index = int(user_ans)
                correct_option_index = int(correct_ans)
                # Map the index back to the option text for reporting
                user_response_text = q['options'][user_option_index] if 0 <= user_option_index < len(q['options']) else "No Answer"
                correct_response_text = q['options'][correct_option_index]
                if user_option_index == correct_option_index:
                    is_correct = True
            except:
                user_response_text = "No Answer / Invalid Selection"
                # Safely try to get the correct option text
                try:
                     correct_response_text = q['options'][int(correct_ans)]
                except:
                     correct_response_text = correct_ans

        
        elif q['type'] == 'ShortAnswer':
            user_response_text = user_ans
            correct_response_text = correct_ans
            # Simple case-insensitive match for scoring
            if user_ans.strip().lower() == correct_ans.strip().lower():
                is_correct = True

        
        # Status
        status = "Correct" if is_correct else "Incorrect"
        # Senior Dev: Use proper color definition for robustness
        status_color = colors.green if is_correct else colors.red
        Story.append(Paragraph(f"<b>Status:</b> <font color='{status_color.hexa() or '#000000'}'>{status}</font>", styles['Normal']))
        
        # Answers
        Story.append(Paragraph(f"<b>Your Answer:</b> {user_response_text}", styles['Normal']))
        Story.append(Paragraph(f"<b>Correct Answer:</b> {correct_response_text}", styles['Normal']))
        
        # Explanation
        Story.append(Paragraph(f"<b>Explanation:</b> {q['explanation']}", styles['Normal']))
        Story.append(Spacer(1, 12)) # Add space after each question

    # Build PDF
    doc.build(Story)
    
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data


# --- Django View Functions ---

# @csrf_exempt <--- REMOVED THIS INSECURE DECORATOR
def analyze_video_api(request):
    """
    API endpoint to initiate video analysis and Gemini generation.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Only POST method is allowed."}, status=405)

    try:
        data = json.loads(request.body)
        video_url = data.get('video_url')
        video_id = data.get('video_id') # Should be extracted by frontend, but re-validate
        
        if not video_id:
            video_id = extract_video_id(video_url)

        if not video_id:
            return JsonResponse({"status": "error", "message": "Invalid or missing YouTube video URL."}, status=400)

        # 1. Fetch Transcript
        transcript = get_youtube_transcript(video_id)
        
        # 2. Generate Summary and Quiz via Gemini
        analysis_result = generate_gemini_analysis(video_url, transcript, video_id)
        
        if "error" in analysis_result:
            return JsonResponse({"status": "error", "message": analysis_result['error'], "details": analysis_result['details']}, status=500)
            
        # 3. Compile final response data
        response_data = {
            "status": "success",
            "summary": analysis_result["summary"],
            "quiz_questions": analysis_result["quiz_questions"],
            # Return transcript string for the Notes/Analysis tab
            "transcript": transcript, 
            "gemini_generated_analysis": analysis_result.get("gemini_generated_analysis", None)
        }
        
        return JsonResponse(response_data)

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON payload."}, status=400)
    except Exception as e:
        logger.exception(f"Error in analyze_video_api: {e}")
        return JsonResponse({"status": "error", "message": f"A server error occurred: {e}"}, status=500)


# @csrf_exempt <--- REMOVED THIS INSECURE DECORATOR
def submit_quiz_api(request):
    """
    API endpoint to score the quiz and generate a PDF report.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Only POST method is allowed."}, status=405)

    try:
        data = json.loads(request.body)
        video_id = data.get('video_id')
        quiz_data = data.get('quiz_data', [])
        user_answers = data.get('user_answers', {}) # Dictionary of {"0": "ans", "1": "1"}
        
        if not video_id or not quiz_data:
            return JsonResponse({"status": "error", "message": "Invalid payload for quiz submission."}, status=400)

        final_score = 0
        total_questions = len(quiz_data)
        
        # 1. Score the quiz
        for i, q in enumerate(quiz_data):
            q_index = str(i)
            is_correct = False
            # Senior Dev: Strip leading/trailing whitespace from user and correct answers for robust comparison
            user_ans = user_answers.get(q_index, '').strip()
            correct_ans = q.get('correct_answer', '').strip()

            if q.get('type') == 'MCQ':
                try:
                    # Compare user's selected index (string) to the correct index (string)
                    if user_ans == correct_ans:
                        is_correct = True
                except:
                    pass # User response was invalid or missing

            elif q.get('type') == 'ShortAnswer':
                # For ShortAnswer, perform a simple case-insensitive match
                if user_ans and user_ans.lower() == correct_ans.lower():
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
    View to handle direct links to a video analysis page by pre-populating the video input.
    """
    context = {'pre_selected_video_id': video_id}
    return render(request, 'learnflow.html', context)