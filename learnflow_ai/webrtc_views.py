"""
WebRTC and Live Classroom API endpoints.

Provides:
- WebRTC token generation (LiveKit, Agora, Janus)
- Live call information
- Audio/video configuration
"""

import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.middleware.csrf import get_token

from .webrtc_utils import get_webrtc_config, WEBRTC_PROVIDER

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(["POST"])
def webrtc_token(request):
    """
    Generate a WebRTC token for a user to join a live call.
    
    Request body:
    {
        "user_id": "unique-user-id",
        "call_id": "call-room-id",
        "is_host": false
    }
    
    Response (LiveKit):
    {
        "provider": "livekit",
        "token": "jwt-token",
        "url": "wss://...",
        "room": "call-id"
    }
    
    Response (Agora):
    {
        "provider": "agora",
        "token": "token-string",
        "appId": "agora-app-id",
        "channel": "call-id",
        "uid": "user-id"
    }
    """
    try:
        data = json.loads(request.body)
        
        user_id = data.get('user_id')
        call_id = data.get('call_id')
        is_host = data.get('is_host', False)
        
        if not user_id or not call_id:
            return JsonResponse({
                'error': 'Missing user_id or call_id'
            }, status=400)
        
        # Get WebRTC configuration for the provider
        config = get_webrtc_config(user_id, call_id, is_host)
        
        if not config:
            return JsonResponse({
                'error': f'WebRTC provider {WEBRTC_PROVIDER} is not properly configured',
                'provider': WEBRTC_PROVIDER
            }, status=500)
        
        logger.info('Generated WebRTC token for user %s in call %s (provider: %s)',
                   user_id, call_id, config['provider'])
        
        return JsonResponse(config)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error('Error generating WebRTC token: %s', e)
        return JsonResponse({
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def webrtc_config(request):
    """
    Get WebRTC configuration info (provider, features, etc).
    
    Response:
    {
        "provider": "livekit",
        "features": {
            "video": true,
            "audio": true,
            "screen_share": true,
            "recording": true
        },
        "limits": {
            "max_participants": 100,
            "max_bandwidth_mbps": 50
        }
    }
    """
    config_info = {
        'provider': WEBRTC_PROVIDER,
        'features': {
            'video': True,
            'audio': True,
            'screen_share': WEBRTC_PROVIDER in ['livekit', 'janus'],
            'recording': WEBRTC_PROVIDER in ['livekit'],
            'data_channel': True,
        },
        'limits': {},
    }
    
    if WEBRTC_PROVIDER == 'livekit':
        config_info['limits'] = {
            'max_participants': 1000,
            'max_bandwidth_mbps': 100,
        }
    elif WEBRTC_PROVIDER == 'agora':
        config_info['limits'] = {
            'max_participants': 5000,
            'max_bandwidth_mbps': 100,
        }
    elif WEBRTC_PROVIDER == 'janus':
        config_info['limits'] = {
            'max_participants': 100,
            'max_bandwidth_mbps': 50,
        }
    
    return JsonResponse(config_info)


@require_http_methods(["GET"])
def csrf_token_view(request):
    """
    Get a CSRF token for WebSocket and form submissions.
    """
    token = get_token(request)
    return JsonResponse({'csrfToken': token})
