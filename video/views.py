# video/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Video
from .forms import VideoForm
from django.http import Http404

@login_required
def video_list(request):
    """
    Renders a list of all available videos.
    """
    videos = Video.objects.all().order_by('-created_at')
    return render(request, 'video/video_list.html', {'videos': videos})

@login_required
def video_detail(request, video_id):
    """
    Renders the detail page for a single video.
    """
    video = get_object_or_404(Video, pk=video_id)
    return render(request, 'video/video_detail.html', {'video': video})

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
    return render(request, 'video/video_upload.html', {'form': form})

@login_required
def teacher_dashboard(request):
    """
    Displays a dashboard of videos uploaded by the current user.
    """
    user_videos = Video.objects.filter(teacher=request.user).order_by('-created_at')
    return render(request, 'video/teacher_dashboard.html', {'user_videos': user_videos})

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

    return render(request, 'video/video_edit.html', {'form': form, 'video': video})

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

    return render(request, 'video/video_delete_confirm.html', {'video': video})
