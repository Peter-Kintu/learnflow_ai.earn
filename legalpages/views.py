import os
import logging
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
# Import additional specific exceptions that might cause a 500 if unhandled
from youtube_transcript_api._errors import CouldNotRetrieveTranscript, VideoUnavailable 
from urllib.parse import urlparse, parse_qs
import time 
import json 

# Initialize logger
logger = logging.getLogger(__name__)

# Helper function to extract the video ID from a YouTube URL
def extract_video_id(url):
    """
    Extracts the YouTube video ID from various URL formats (watch, youtu.be, live).
    """
    if "youtu.be" in url:
        # Handles short URL format
        return url.split("/")[-1]
    
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
    # Assuming 'learnflow.html' is the main app page.
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
    It loads the main analysis page (learnflow.html) which can then load the video.
    """
    return render(request, 'learnflow.html', {'pre_selected_video_id': video_id})


# ----------------------------------------------------------------------

# --- API View (Real Transcript Logic) ---

@csrf_exempt
def fetch_transcript_api(request):
    """
    API endpoint to fetch the real transcript from a YouTube link using the 
    youtube-transcript-api Python library.
    """
    if request.method == 'POST':
        video_id = None 
        
        try:
            # 1. Get and Sanitize the YouTube link
            link = request.POST.get('youtube_link', '').strip() 

            if link.count("http") > 1:
                logger.warning(f"Malformed link detected and sanitized: {link}")
                link = link[link.find("http", 1):]

            if not link:
                logger.error("POST request received without 'youtube_link' parameter.")
                return JsonResponse({"status": "error", "message": "No YouTube link provided."}, status=400)
            
            video_id = extract_video_id(link)
            
            logger.info(f"Attempting transcript fetch. Received link: {link}, Extracted ID: {video_id}")
            
            if not video_id:
                logger.warning(f"Could not extract video ID from link: {link}")
                return JsonResponse({"status": "error", "message": "Could not extract a valid YouTube video ID."}, status=400)
            
            # 2. Fetch the transcript. (Using get_transcript for maximum compatibility)
            # FIX: This uses the most stable, universally supported method to avoid the AttributeError.
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
            
            # 3. Concatenate all transcript segments into a single string
            full_transcript = " ".join([item['text'] for item in transcript_list])
            
            # 4. Return the successful response
            response_data = {
                "status": "success",
                "transcript": full_transcript,
                "video_id": video_id
            }
            return JsonResponse(response_data)

        # Handle specific errors from the transcript API (return 404)
        except (TranscriptsDisabled, NoTranscriptFound, CouldNotRetrieveTranscript, VideoUnavailable) as e:
             logger.warning(f"Transcript unavailable for {video_id}: {str(e)}")
             return JsonResponse({
                "status": "error", 
                "message": f"Transcript not available. This video either has transcripts disabled, is unavailable, or the API failed to retrieve it. Error: {str(e)}"}, status=404)
        
        except Exception as e:
            # Catch all other exceptions (Network errors, Rate Limiting, unexpected crashes)
            logger.exception(f"A critical, unhandled error occurred during transcript fetch for {video_id}.")
            
            return JsonResponse({
                "status": "error", 
                "message": "A critical server error occurred. Please try again or check the server logs."}, status=500)
        
    # Handle non-POST requests
    return JsonResponse({"status": "error", "message": "Invalid request method. Must use POST."}, status=400)