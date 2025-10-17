from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Video
from .forms import VideoForm
from django.http import Http404
from urllib.parse import urlparse, parse_qs

# Helper function to get the YouTube embed URL from a standard URL
def get_embed_url(youtube_url):
    """
    Parses a standard YouTube URL and returns the embed URL format.
    
    Args:
        youtube_url (str): The standard YouTube URL.
    
    Returns:
        str: The embed URL or None if the URL is invalid.
    """
    try:
        query = urlparse(youtube_url)
        if query.hostname in ['www.youtube.com', 'youtube.com', 'youtu.be']:
            if query.hostname == 'youtu.be':
                # Handle short URLs like https://youtu.be/abc123
                video_id = query.path[1:]
            else:
                # Handle standard URLs like https://www.youtube.com/watch?v=abc123
                video_id = parse_qs(query.query).get("v", [None])[0]
            
            if video_id:
                return f"https://www.youtube.com/embed/{video_id}"
    except Exception:
        pass # Fallback to None
    
    return None

@login_required
def video_list(request):
    """
    Renders a list of all available videos.
    """
    videos = Video.objects.all().order_by('-created_at')
    return render(request, 'video/video_list.html', {'videos': videos, 'show_ads': True})

@login_required
def video_detail(request, video_id):
    """
    Renders the detail page for a single video.
    """
    video = get_object_or_404(Video, pk=video_id)
    embed_url = get_embed_url(video.url)
    
    context = {
        'video': video,
        'embed_url': embed_url,
        'show_ads': True
    }
    return render(request, 'video/video_detail.html', context)

@login_required
def create_video(request):
    """
    Allows a teacher to upload a new video.
    """
    if request.method == 'POST':
        form = VideoForm(request.POST)
        if form.is_valid():
            video = form.save(commit=False)
            video.teacher = request.user
            video.save()
            # This is where the ManyToMany relationship is saved.
            # It must be done after the video object has been saved to the database.
            form.save_m2m()
            messages.success(request, f'"{video.title}" has been uploaded successfully!')
            return redirect('video:video_list')
    else:
        form = VideoForm()
    return render(request, 'video/video_upload.html', {'form': form, 'show_ads': True})

@login_required
def teacher_dashboard(request):
    """
    Displays a dashboard of videos uploaded by the current user.
    """
    user_videos = Video.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'video/teacher_dashboard.html', {'user_videos': user_videos, 'show_ads': True})

@login_required
def edit_video(request, video_id):
    """
    Allows a teacher to edit an existing video.
    """
    video = get_object_or_404(Video, pk=video_id)
    
    if video.teacher != request.user:
        raise Http404
        
    if request.method == 'POST':
        form = VideoForm(request.POST, instance=video)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{video.title}" has been updated successfully!')
            return redirect('video:teacher_dashboard')
    else:
        form = VideoForm(instance=video)

    return render(request, 'video/video_edit.html', {'form': form, 'video': video, 'show_ads': True})

@login_required
def delete_video(request, video_id):
    """
    Allows a teacher to delete a video.
    """
    video = get_object_or_404(Video, pk=video_id)
    
    if video.teacher != request.user:
        raise Http404
        
    if request.method == 'POST':
        video.delete()
        messages.success(request, f'"{video.title}" has been deleted successfully.')
        return redirect('video:teacher_dashboard')

    return render(request, 'video/video_delete_confirm.html', {'video': video, 'show_ads': True})
