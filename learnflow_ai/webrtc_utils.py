"""
WebRTC utilities for video streaming via LiveKit, Agora, or Janus.

This module provides token generation and session management for real-time
video streaming in live classroom sessions.
"""

import os
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# WebRTC Provider Configuration
WEBRTC_PROVIDER = os.environ.get('WEBRTC_PROVIDER', 'livekit')  # 'livekit', 'agora', or 'janus'

# LiveKit Configuration
LIVEKIT_URL = os.environ.get('LIVEKIT_URL', '')
LIVEKIT_API_KEY = os.environ.get('LIVEKIT_API_KEY', '')
LIVEKIT_API_SECRET = os.environ.get('LIVEKIT_API_SECRET', '')

# Agora Configuration
AGORA_APP_ID = os.environ.get('AGORA_APP_ID', '')
AGORA_APP_CERTIFICATE = os.environ.get('AGORA_APP_CERTIFICATE', '')

# Janus Configuration
JANUS_URL = os.environ.get('JANUS_URL', '')
JANUS_ADMIN_SECRET = os.environ.get('JANUS_ADMIN_SECRET', '')


class LiveKitTokenGenerator:
    """Generate access tokens for LiveKit SFU."""
    
    @staticmethod
    def generate_token(
        user_id: str,
        room_name: str,
        is_host: bool = False,
        duration_minutes: int = 60
    ) -> Optional[str]:
        """
        Generate a LiveKit access token.
        
        Args:
            user_id: Unique user identifier
            room_name: Name of the video room (call_id)
            is_host: Whether this user can publish video/audio
            duration_minutes: Token validity duration
            
        Returns:
            JWT token string or None if LiveKit is not configured
        """
        if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
            logger.warning('LiveKit is not configured. Set LIVEKIT_API_KEY and LIVEKIT_API_SECRET.')
            return None
        
        try:
            from livekit import AccessToken, VideoGrants
            
            token = AccessToken(
                LIVEKIT_API_KEY,
                LIVEKIT_API_SECRET,
                identity=user_id,
                name=f"User-{user_id[:8]}",
                duration=duration_minutes * 60,
                grants=VideoGrants(
                    room_join=True,
                    room=room_name,
                    can_publish=is_host,  # Only host can publish video/audio
                    can_subscribe=True,   # Everyone can subscribe to others
                    can_publish_data=True,  # Can publish data channels
                ),
            )
            
            logger.debug('Generated LiveKit token for user %s in room %s (is_host: %s)', 
                        user_id, room_name, is_host)
            return token.to_jwt()
        
        except ImportError:
            logger.error('livekit-python SDK not installed. Install with: pip install livekit-python')
            return None
        except Exception as e:
            logger.error('Failed to generate LiveKit token: %s', e)
            return None


class AgoraTokenGenerator:
    """Generate access tokens for Agora SFU."""
    
    @staticmethod
    def generate_token(
        user_id: str,
        channel_name: str,
        is_host: bool = False,
        expiration_seconds: int = 3600
    ) -> Optional[str]:
        """
        Generate an Agora access token.
        
        Args:
            user_id: Unique user identifier (UID)
            channel_name: Name of the video channel (room_id)
            is_host: Whether this user can publish (publisher or subscriber)
            expiration_seconds: Token validity duration
            
        Returns:
            Token string or None if Agora is not configured
        """
        if not AGORA_APP_ID or not AGORA_APP_CERTIFICATE:
            logger.warning('Agora is not configured. Set AGORA_APP_ID and AGORA_APP_CERTIFICATE.')
            return None
        
        try:
            from agora_token_builder import RtcTokenBuilder, Role_Publisher, Role_Subscriber
            
            # Use publisher role for hosts, subscriber for guests
            role = Role_Publisher if is_host else Role_Subscriber
            
            token = RtcTokenBuilder.buildTokenWithUid(
                AGORA_APP_ID,
                AGORA_APP_CERTIFICATE,
                channel_name,
                int(user_id),  # Agora expects numeric UID
                role,
                expiration_seconds
            )
            
            logger.debug('Generated Agora token for user %s in channel %s (role: %s)',
                        user_id, channel_name, 'Publisher' if is_host else 'Subscriber')
            return token
        
        except ImportError:
            logger.error('agora-token-builder SDK not installed. Install with: pip install agora-token-builder')
            return None
        except Exception as e:
            logger.error('Failed to generate Agora token: %s', e)
            return None


class JanusSessionManager:
    """Manage sessions for Janus WebRTC gateway."""
    
    @staticmethod
    async def create_session(user_id: str, room_id: str) -> Optional[Dict[str, Any]]:
        """
        Create a Janus session for a user.
        
        Args:
            user_id: Unique user identifier
            room_id: Room identifier (call_id)
            
        Returns:
            Session info dict with session_id, handle_id, or None if failed
        """
        if not JANUS_URL:
            logger.warning('Janus is not configured. Set JANUS_URL.')
            return None
        
        try:
            import aiohttp
            
            async with aiohttp.ClientSession() as session:
                # Create Janus session
                async with session.post(f'{JANUS_URL}/janus', json={
                    'janus': 'create',
                    'transaction': f'create-{user_id}'
                }) as resp:
                    data = await resp.json()
                    
                    if data.get('janus') != 'success':
                        logger.error('Failed to create Janus session: %s', data)
                        return None
                    
                    session_id = data['data']['id']
                    
                    # Attach videoroom plugin
                    async with session.post(f'{JANUS_URL}/janus/{session_id}', json={
                        'janus': 'attach',
                        'plugin': 'janus.plugin.videoroom',
                        'transaction': f'attach-{user_id}'
                    }) as resp2:
                        data2 = await resp2.json()
                        
                        if data2.get('janus') != 'success':
                            logger.error('Failed to attach videoroom plugin: %s', data2)
                            return None
                        
                        handle_id = data2['data']['id']
                        
                        logger.debug('Created Janus session for user %s: session_id=%s, handle_id=%s',
                                    user_id, session_id, handle_id)
                        
                        return {
                            'session_id': session_id,
                            'handle_id': handle_id,
                            'user_id': user_id,
                            'room_id': room_id,
                        }
        
        except ImportError:
            logger.error('aiohttp SDK not installed. Install with: pip install aiohttp')
            return None
        except Exception as e:
            logger.error('Failed to create Janus session: %s', e)
            return None


def get_webrtc_config(
    user_id: str,
    call_id: str,
    is_host: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Get WebRTC configuration based on the configured provider.
    
    Returns a dict with:
    - 'provider': The service name ('livekit', 'agora', 'janus')
    - 'token': Access token (for LiveKit/Agora)
    - 'url': Server URL (for LiveKit/Janus)
    - 'room': Room/channel name
    - 'config': Provider-specific configuration
    """
    provider = WEBRTC_PROVIDER.lower()
    
    if provider == 'livekit':
        token = LiveKitTokenGenerator.generate_token(user_id, call_id, is_host)
        if not token:
            return None
        return {
            'provider': 'livekit',
            'token': token,
            'url': LIVEKIT_URL,
            'room': call_id,
        }
    
    elif provider == 'agora':
        token = AgoraTokenGenerator.generate_token(
            user_id,
            call_id,
            is_host
        )
        if not token:
            return None
        return {
            'provider': 'agora',
            'token': token,
            'appId': AGORA_APP_ID,
            'channel': call_id,
            'uid': user_id,
        }
    
    elif provider == 'janus':
        return {
            'provider': 'janus',
            'url': JANUS_URL,
            'room': call_id,
            # Session creation is async, handled separately
        }
    
    else:
        logger.error('Unknown WebRTC provider: %s', provider)
        return None
