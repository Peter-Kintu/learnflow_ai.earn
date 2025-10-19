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
from google.genai import types # Import types for schema definition

# Initialize logger
logger = logging.getLogger(__name__)

# --- AI Client Initialization ---
# It is assumed that the GEMINI_API_KEY is set in your environment
try:
    client = genai.Client()
except Exception as e:
    logger.error(f"Error initializing Gemini client: {e}")
    client = None
    
# --- Helper Functions (UNCHANGED) ---

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
        if 'v' in query_params:
            return query_params['v'][0]
    
    # Fallback/default logic
    return None

def fetch_transcript(video_id):
    """
    Fetches the full English transcript for a given YouTube video ID.
    Returns the transcript text or an error message string on failure.
    """
    if not video_id:
        return "Video ID is missing or invalid."
    
    try:
        # Attempt to find an English transcript
        transcript_list = YouTubeTranscriptApi.list(video_id)
        transcript = transcript_list.find_transcript(['en', 'en-US', 'en-GB'])
        
        if transcript:
            # Fetch the actual transcript and combine the text parts
            full_transcript = " ".join([item['text'] for item in transcript.fetch()])
            return full_transcript
        
        return "No English transcript found for this video."

    except NoTranscriptFound:
        logger.warning(f"Transcript not found for video ID: {video_id}")
        return "No English transcript found for this video."
    except TranscriptsDisabled:
        logger.warning(f"Transcripts are disabled for video ID: {video_id}")
        return "Transcripts are disabled by the video creator."
    except (CouldNotRetrieveTranscript, VideoUnavailable) as e:
        logger.error(f"Failed to retrieve transcript for {video_id}: {str(e)}")
        return "Failed to retrieve transcript due to video inaccessibility or API error."
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching transcript for {video_id}: {e}")
        return "An unexpected server error occurred during transcript fetching."

def generate_ai_content(transcript_text, model=client.models.get('gemini-2.5-flash')):
    """
    Uses the Gemini API to generate a summary and quiz from the transcript.
    """
    if not client:
        return {"summary": "AI client not initialized.", "quiz": []}

    prompt = (
        "Based on the following YouTube video transcript, perform two tasks:\n"
        "1. Create a detailed, bulleted **Summary** that captures all key concepts and facts.\n"
        "2. Generate a **Quiz** of exactly **3 multiple-choice questions** based on the summary and transcript. Each question must have exactly **4 options**.\n"
        "Return the response as a single JSON object. DO NOT include any text outside of the JSON object.\n\n"
        "TRANSCRIPT:\n"
        f"---{transcript_text}---"
    )

    # Define the required JSON output schema for the model
    # The 'answer' is requested as a string here for the AI to fill, 
    # and will be converted to 'correctAnswerIndex' later.
    quiz_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "question": {"type": "string", "description": "The quiz question."},
            "options": {"type": "array", "items": {"type": "string"}, "description": "Exactly four answer options."},
            "answer": {"type": "string", "description": "The exact option string that is the correct answer."}
        },
        required=["question", "options", "answer"]
    )

    response_schema = types.Schema(
        type=types.Type.OBJECT,
        properties={
            "summary": {"type": "string", "description": "A detailed, bulleted summary of the video transcript."},
            "quiz": {"type": "array", "items": quiz_schema, "description": "An array of exactly 3 multiple-choice questions."}
        },
        required=["summary", "quiz"]
    )

    try:
        response = model.generate_content(
            prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
            )
        )
        # The response text is a JSON string
        return json.loads(response.text)
    
    except APIError as e:
        logger.exception(f"Gemini API Error: {e}")
        return {"summary": f"AI Content Generation Failed (API Error): {e}", "quiz": []}
    except Exception as e:
        logger.exception(f"General error during AI generation: {e}")
        return {"summary": f"AI Content Generation Failed (General Error): {e}", "quiz": []}

# --- Django Views (UNCHANGED structure, but corrected function names) ---

def privacy_policy(request):
    return JsonResponse({"message": "Privacy Policy Placeholder"})

def terms_conditions(request):
    return JsonResponse({"message": "Terms and Conditions Placeholder"})

def about_us(request):
    return JsonResponse({"message": "About Us Placeholder"})

def contact_us(request):
    return JsonResponse({"message": "Contact Us Placeholder"})

def sitemap_page(request):
    return JsonResponse({"message": "Sitemap Placeholder"})

def video_analysis_view(request, video_id):
    # This view is for a specific video and likely renders the template with data
    return JsonResponse({"message": f"Video Analysis View Placeholder for ID: {video_id}"})

def learnflow_overview(request):
    # This view likely renders the learnflow_overview.html template
    return render(request, 'learnflow_overview.html')

def learnflow_video_analysis(request):
    """Renders the main application HTML page."""
    # This view is simple and just serves the HTML
    return render(request, 'learnflow.html')

@csrf_exempt
def analyze_video_api(request):
    """
    API endpoint to fetch transcript and generate AI summary/quiz.
    """
    # 1. Input Validation and Setup
    if request.method != 'POST':
        return JsonResponse({"status": "error", "message": "Invalid request method. Must use POST."}, status=400)

    video_id = None # Initialize outside try block for wider scope
    try:
        data = json.loads(request.body)
        video_link = data.get('video_link')
        
        if not video_link:
            return JsonResponse({'status': 'error', 'message': 'Missing video_link parameter.'}, status=400)

        video_id = extract_video_id(video_link)
        if not video_id:
            return JsonResponse({'status': 'error', 'message': 'Could not extract valid YouTube video ID.'}, status=400)

        # 2. Fetch Transcript
        transcript_text = fetch_transcript(video_id)
        # transcript_found is true if the text is not one of the error strings
        transcript_found = not transcript_text.startswith("No English transcript found") and \
                           not transcript_text.startswith("Transcripts are disabled") and \
                           not transcript_text.startswith("Failed to retrieve transcript") and \
                           not transcript_text.startswith("An unexpected server error")
        
        if not transcript_found:
            message = transcript_text
            # Return a non-critical error status for frontend to display the message
            return JsonResponse({'status': 'error', 'message': message}, status=500)

        # 3. Generate AI Content
        ai_data = generate_ai_content(transcript_text)
        
        # 4. CRITICAL FIX: Process Quiz Data for Frontend Compatibility
        processed_quiz = []
        for q in ai_data.get("quiz", []):
            try:
                # Find the index of the correct answer string within the options array
                # This is the conversion from AI's string 'answer' to client's integer 'correctAnswerIndex'
                correct_index = q["options"].index(q["answer"])
            except ValueError:
                # Fallback if the AI's 'answer' string is not exactly in the 'options' list
                logger.warning(f"AI answer string '{q.get('answer')}' not found in options for {video_id}.")
                correct_index = -1 
                
            processed_quiz.append({
                "question": q.get("question", "N/A"),
                "options": q.get("options", []),
                "correctAnswerIndex": correct_index, # <-- Frontend now expects this integer index
            })

        # 5. Prepare and return final response
        response_data = {
            "status": "success",
            "summary": ai_data.get("summary", "Summary could not be generated."),
            "quiz": processed_quiz, # Use the processed data
            "transcript_text": transcript_text, # Include the full transcript for the transcript tab
            "transcript_status": "FOUND" if transcript_found else "NOT_FOUND",
            "video_id": video_id
        }
        return JsonResponse(response_data)

    # Catch remaining general exceptions
    except APIError as e:
        logger.exception(f"Gemini API Error for {video_id}: {str(e)}")
        return JsonResponse({
            "status": "error", 
            "message": f"AI service failed (Gemini API Error). Please check your API key and quota or try again."}, status=503)

    except json.JSONDecodeError:
        logger.exception(f"AI response was not valid JSON for {video_id}.")
        return JsonResponse({
            "status": "error", 
            "message": "AI service returned an invalid response format."}, status=500)

    except Exception as e:
        # Catch all other exceptions 
        logger.exception(f"A critical, unhandled error occurred during fetch/AI processing for {video_id}. Error: {e}")
        return JsonResponse({
            "status": "error", 
            "message": "A critical server error occurred during processing. Please try again."}, status=500)