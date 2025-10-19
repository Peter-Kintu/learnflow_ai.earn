import os
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from urllib.parse import urlparse, parse_qs
import json 

# Imports for Transcript Fetching
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api._errors import CouldNotRetrieveTranscript, VideoUnavailable 

# Imports for Gemini AI
import google.genai as genai
from google.genai.errors import APIError
from google.genai import types # <--- FIXED: RE-ADDED MISSING IMPORT

# Initialize logger
logger = logging.getLogger(__name__)

# Helper function to extract the video ID from a YouTube URL
def extract_video_id(url):
    """
    Extracts the YouTube video ID from various URL formats (watch, youtu.be, live).
    """
    if "youtu.be" in url:
        return url.split("/")[-1].split("?")[0]
    
    # Handle /live/ URLs
    if "youtube.com/live/" in url:
        return url.split("/")[-1].split("?")[0]
    
    # Handle standard watch URLs
    parsed_url = urlparse(url)
    if parsed_url.query:
        query_params = parse_qs(parsed_url.query)
        # Gets the 'v' parameter which holds the video ID
        return query_params.get('v', [None])[0]
        
    return None

def fetch_transcript_robust(video_id):
    """
    Fetches the full English transcript. Returns the text or a fallback message string.
    
    IMPROVED: Uses list_transcripts and find_transcript with auto_generate=True 
    to robustly attempt to retrieve both manual and auto-generated captions.
    """
    if not video_id:
        return "Video ID is missing or invalid."
    
    # We will prioritize English (en) and its common variants.
    target_languages = ['en', 'en-US', 'en-GB'] 

    try:
        # 1. Get all available transcripts (manual and auto-generated flags)
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # 2. Find the best English transcript, allowing auto-generation as a fallback
        # auto_generate=True is the key to fetching captions when manual ones are missing.
        transcript_obj = transcript_list.find_transcript(target_languages, auto_generate=True)
        
        # 3. Fetch the content
        transcript_data = transcript_obj.fetch()
        
        # 4. Process the fetched data into a single string
        full_transcript = " ".join([item['text'] for item in transcript_data])
        return full_transcript
        
    except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript, VideoUnavailable) as e:
        logger.warning(f"Transcript unavailable for {video_id}. Error: {str(e)}")
        # Return a consistent fallback message for the AI model to handle
        return f"NO TRANSCRIPT: Transcript is unavailable for this video. Please summarize based on this fact."
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching transcript for {video_id}: {e}")
        return f"NO TRANSCRIPT: A critical error occurred during transcript fetching: {e}"


# --- Main Application Views ---

def learnflow_video_analysis(request):
    """
    Renders the main template containing the client-side HTML and JavaScript.
    This is the core video analysis page (learnflow.html).
    """
    return render(request, 'learnflow.html', {
        'api_key': os.getenv('GEMINI_API_KEY') # Passes the API key to the template context
    })

def learnflow_overview(request):
    """
    Renders the overview page for LearnFlow.
    """
    return render(request, 'learnflow_overview.html') 

# --- Static Pages Views ---

def privacy_policy(request):
    return render(request, 'privacy.html')

def terms_conditions(request):
    return render(request, 'terms.html')

def about_us(request):
    return render(request, 'about.html')

def contact_us(request):
    return render(request, 'contact.html')

def sitemap_page(request):
    return render(request, 'sitemap.html')
    
def video_analysis_view(request, video_id):
    """
    Placeholder view for a dynamic video analysis page.
    """
    return render(request, 'learnflow.html', {'pre_selected_video_id': video_id})


# ----------------------------------------------------------------------

# --- API View (Real Transcript Logic & AI Analysis) ---

@csrf_exempt
def analyze_video_api(request): 
    """
    API endpoint to fetch transcript and generate AI summary and quiz.
    """
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Invalid request method. Must use POST."}, status=400)

    video_id = None
    transcript_text = None
        
    # Initialize Gemini Client and API Key Check
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found in environment variables.")
        return JsonResponse({"status": "error", "message": "AI service not configured."}, status=500)
    
    try:
        # 1. Get Video Link from JSON body (CRITICAL FIX: Use json.loads(request.body))
        data = json.loads(request.body)
        video_link = data.get('video_link', '').strip()
        
        if not video_link:
            return JsonResponse({"status": "error", "message": "No YouTube link provided."}, status=400)
        
        video_id = extract_video_id(video_link)
        if not video_id:
            return JsonResponse({"status": "error", "message": "Could not extract a valid YouTube video ID."}, status=400)
        
        logger.info(f"Analysis request received for video ID: {video_id}")
        
        # --- 2. Transcript Fetch Attempt (Using robust helper) ---
        transcript_text = fetch_transcript_robust(video_id)

        # Check if the result is a fallback message indicating failure
        transcript_found = not transcript_text.startswith("NO TRANSCRIPT")
        
        # --- 3. AI Summarization and Quiz Generation ---
        client = genai.Client(api_key=api_key)
        
        prompt = (
            "Based on the following video content, perform two tasks:\n"
            "1. **SUMMARY:** Summarize the main topics and key takeaways in a concise, informative paragraph.\n"
            "2. **QUIZ:** Generate 3 multiple-choice questions (MCQs) that test comprehension. Provide each question with 4 options and identify the correct answer. The quiz must be answerable from the summary/content.\n\n"
            "Format your response strictly as a JSON object with two top-level keys: 'summary' (string) and 'quiz' (list of question objects).\n\n"
            f"Video Content:\n\n{transcript_text}"
        )

        # Define schema using the imported 'types'
        response_schema = types.Schema(
            type=types.Type.OBJECT,
            properties={
                "summary": {"type": "string"},
                "quiz": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string"},
                            "options": {"type": "array", "items": {"type": "string"}},
                            "answer": {"type": "string"} # 'answer' holds the correct option string
                        },
                        "required": ["question", "options", "answer"]
                    }
                }
            },
            required=["summary", "quiz"]
        )

        # Generate content and request JSON output
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig( # <--- Using 'types' here
                response_mime_type="application/json",
                response_schema=response_schema,
            )
        )

        # 4. Process and Return the successful response
        ai_data = json.loads(response.text)
        
        # Convert AI's 'answer' string to client's required 'correctAnswerIndex' integer
        processed_quiz = []
        for q in ai_data.get("quiz", []):
            correct_index = -1
            try:
                # Find the index of the correct answer string within the options array
                correct_index = q["options"].index(q["answer"])
            except ValueError:
                logger.warning(f"AI answer string '{q.get('answer')}' not found in options for {video_id}.")
                
            processed_quiz.append({
                "question": q.get("question", "N/A"),
                "options": q.get("options", []),
                "correctAnswerIndex": correct_index, # <-- Frontend now expects this integer index
            })


        response_data = {
            "status": "success",
            "summary": ai_data.get("summary", "Summary could not be generated."),
            "quiz": processed_quiz,
            "transcript_status": "FOUND" if transcript_found else "NOT_FOUND",
            "video_id": video_id,
            # If transcript failed, the transcript_text is the fallback message
            "transcript_text": transcript_text 
        }
        return JsonResponse(response_data)

    # Catch remaining general exceptions
    except APIError as e:
        logger.exception(f"Gemini API Error for {video_id}: {str(e)}")
        return JsonResponse({
            "status": "error", 
            "message": f"AI service failed (Gemini API Error). Please check your API key and quota."}, status=503)

    except json.JSONDecodeError:
        logger.exception(f"AI response was not valid JSON for {video_id}.")
        return JsonResponse({
            "status": "error", 
            "message": "AI service returned an invalid response format."}, status=500)

    except Exception as e:
        # Catch all other exceptions 
        logger.exception(f"A critical, unhandled error occurred during fetch/AI processing for {video_id}.")
        return JsonResponse({
            "status": "error", 
            "message": f"A critical server error occurred during processing: {e}"}, status=500)