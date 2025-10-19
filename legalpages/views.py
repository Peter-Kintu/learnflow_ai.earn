from django.shortcuts import render
from django.http import JsonResponse
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
import time # Used for potential simulated delays if needed

# Helper function to extract the video ID from a YouTube URL
def extract_video_id(url):
    """
    Extracts the YouTube video ID from various URL formats (watch, youtu.be).
    """
    if "youtu.be" in url:
        # Handles short URL format
        return url.split("/")[-1]
    
    # Handle standard watch URLs
    parsed_url = urlparse(url)
    if parsed_url.query:
        query_params = parse_qs(parsed_url.query)
        # Gets the 'v' parameter which holds the video ID
        return query_params.get('v', [None])[0]
        
    return None

# --- Main Application Views ---

def learnflow_video_analysis(request):
    """
    Renders the main template containing the client-side HTML and JavaScript.
    This is the core video analysis page (learnflow.html).
    """
    # Assuming 'learnflow.html' is the main app page.
    # The original file name was 'youtubecourse.html' in a comment, but the provided HTML is 'learnflow.html'
    return render(request, 'learnflow.html')

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
    For now, it redirects to the main learnflow_video_analysis page.
    """
    # This dynamic URL is likely not intended to be a unique page, 
    # but rather a way to load the main analysis page with a video pre-selected.
    # To fix the NoReverseMatch, we must include this function.
    return render(request, 'learnflow.html', {'pre_selected_video_id': video_id})


# --- API View (Real Transcript Logic) ---

def fetch_transcript_api(request):
    """
    API endpoint to fetch the real transcript from a YouTube link using the 
    youtube-transcript-api Python library.
    """
    if request.method == 'POST':
        try:
            # 1. Get the YouTube link from the POST data
            link = request.POST.get('youtube_link')
            if not link:
                return JsonResponse({"status": "error", "message": "No YouTube link provided."}, status=400)
            
            video_id = extract_video_id(link)
            if not video_id:
                return JsonResponse({"status": "error", "message": "Could not extract a valid YouTube video ID."}, status=400)
            
            # 2. Fetch the transcript.
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

        except Exception as e:
            # Catch exceptions like "No transcript found" or API errors
            return JsonResponse({
                "status": "error", 
                "message": f"Failed to fetch transcript. Note: Not all YouTube videos have transcripts enabled. Error: {str(e)}"
            }, status=500)
        
    return JsonResponse({"status": "error", "message": "Invalid request method. Must use POST."}, status=400)