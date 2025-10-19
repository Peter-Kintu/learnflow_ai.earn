import os
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

# Imports for Transcript Fetching
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api._errors import CouldNotRetrieveTranscript, VideoUnavailable 
from urllib.parse import urlparse, parse_qs
import time 
import json 

# Imports for Gemini AI (Requires 'google-genai' package)
import google.genai as genai
from google.genai.errors import APIError

# Initialize logger
logger = logging.getLogger(__name__)

# Helper function to extract the video ID from a YouTube URL
def extract_video_id(url):
    """
    Extracts the YouTube video ID from various URL formats (watch, youtu.be, live).
    """
    if "youtu.be" in url:
        # Handles short URL format and strips any trailing query parameters like '?si=...' on shared links
        return url.split("/")[-1].split("?")[0]
    
    # Handle /live/ URLs
    if "youtube.com/live/" in url:
        # Extracts ID from a /live/ URL, stripping any trailing query params
        return url.split("/")[-1].split("?")[0]
    
    # Handle standard watch URLs
    parsed_url = urlparse(url)
    if parsed_url.query:
        query_params = parse_qs(parsed_url.query)
        # Gets the 'v' parameter which holds the video ID
        return query_params.get('v', [None])[0]
        
    return None

# ----------------------------------------------------------------------

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
def analyze_video_api(request): # <-- CRITICAL: Must be named this way to match urls.py
    """
    API endpoint to fetch transcript and generate AI summary and quiz.
    """
    if request.method == 'POST':
        video_id = None 
        transcript_found = False
        full_transcript = ""
        
        # Initialize Gemini Client (Requires GEMINI_API_KEY environment variable)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables.")
            return JsonResponse({"status": "error", "message": "AI service not configured."}, status=500)
        
        try:
            # 1. Get and Sanitize the YouTube link
            link = request.POST.get('youtube_link', '').strip() 

            if link.count("http") > 1:
                logger.warning(f"Malformed link detected and sanitized: {link}")
                link = link[link.find("http", 1):]

            if not link:
                return JsonResponse({"status": "error", "message": "No YouTube link provided."}, status=400)
            
            # Use the fixed video ID extraction logic
            video_id = extract_video_id(link)
            
            logger.info(f"Attempting transcript fetch. Received link: {link}, Extracted ID: {video_id}")
            
            if not video_id:
                return JsonResponse({"status": "error", "message": "Could not extract a valid YouTube video ID."}, status=400)
            
            
            # --- 2. Transcript Fetch Attempt ---
            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
                full_transcript = " ".join([item['text'] for item in transcript_list])
                transcript_found = True
                logger.info("Transcript successfully retrieved.")
                
            except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript, VideoUnavailable) as e:
                logger.warning(f"Transcript unavailable for {video_id}. Proceeding to AI step. Error: {str(e)}")
                # Set a fallback message for the AI model to use
                full_transcript = f"NO TRANSCRIPT: Video ID {video_id}, Link: {link}."
                transcript_found = False


            # --- 3. AI Summarization and Quiz Generation ---
            client = genai.Client(api_key=api_key)
            
            # Use a single, powerful prompt for both summary and quiz
            prompt = (
                "Based on the following video content, perform two tasks:\n"
                "1. **SUMMARY:** Summarize the main topics and key takeaways in a concise, informative paragraph.\n"
                "2. **QUIZ:** Generate 3 multiple-choice questions (MCQs) that test comprehension. Provide each question with 4 options and identify the correct answer.\n\n"
                "Format your response strictly as a JSON object with two top-level keys: 'summary' (string) and 'quiz' (list of question objects).\n\n"
                f"Video Content:\n\n{full_transcript}"
            )

            # Generate content and request JSON output
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string"},
                            "quiz": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "question": {"type": "string"},
                                        "options": {"type": "array", "items": {"type": "string"}},
                                        "answer": {"type": "string"}
                                    },
                                    "required": ["question", "options", "answer"]
                                }
                            }
                        },
                        "required": ["summary", "quiz"]
                    }
                )
            )

            # 4. Return the successful response
            ai_data = json.loads(response.text)
            
            response_data = {
                "status": "success",
                "summary": ai_data.get("summary", "Summary could not be generated."),
                "quiz": ai_data.get("quiz", []),
                "transcript_status": "FOUND" if transcript_found else "NOT_FOUND",
                "video_id": video_id
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
                "message": "A critical server error occurred during processing. Please try again."}, status=500)
        
    # Handle non-POST requests
    return JsonResponse({"status": "error", "message": "Invalid request method. Must use POST."}, status=400)