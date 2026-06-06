import os
import json
import asyncio
import base64
import logging
import uuid
import time

from channels.generic.websocket import AsyncWebsocketConsumer

logger = logging.getLogger(__name__)

LIVE_LOBBY_GROUP = 'live_calls_lobby'
ACTIVE_LIVE_CALLS = {
    'math-madness': {
        'id': 'math-madness',
        'title': 'Math Mastery Call',
        'host': 'Amina',
        'participants': 12,
        'topic': 'Algebra',
        'status': 'Live'
    },
    'science-depth': {
        'id': 'science-depth',
        'title': 'Science Deep Dive',
        'host': 'David',
        'participants': 8,
        'topic': 'Physics',
        'status': 'Live'
    },
    'swahili-study': {
        'id': 'swahili-study',
        'title': 'Swahili Study Circle',
        'host': 'Grace',
        'participants': 5,
        'topic': 'Language',
        'status': 'Live'
    }
}
ACTIVE_CALL_MEMBERS = {}

# Room-level Gemini session management (ONE per room, shared by all users)
ROOM_GEMINI_SESSIONS = {}  # call_id -> RoomGeminiSession
ROOM_HOSTS = {}  # call_id -> host_user_id


class RoomGeminiSession:
    """Manages a single Gemini Live session shared across all users in a room."""
    
    def __init__(self, call_id, client, config):
        self.call_id = call_id
        self.client = client
        self.config = config
        self.session = None
        self.task = None
        self.is_active = False
        self.audio_queue = []
        
    async def start(self):
        """Start the room's Gemini session."""
        if self.is_active:
            return
        self.is_active = True
        self.task = asyncio.create_task(self._stream_with_gemini())
        
    async def _stream_with_gemini(self):
        """Manage the Gemini Live stream for this room."""
        try:
            # Determine the best available model
            # Fallback order: gemini-2.0-flash-exp (experimental) → gemini-2.0-flash (stable) → gemini-1.5-flash
            available_models = [
                'gemini-2.0-flash-exp',      # Latest experimental
                'gemini-2.0-flash',          # Latest stable
                'gemini-1.5-flash',          # Previous generation
            ]
            
            selected_model = None
            for model_name in available_models:
                try:
                    # Try to connect with this model
                    logger.info('Attempting to connect to Gemini model: %s', model_name)
                    async with self.client.aio.live.connect(model=model_name, config=self.config) as session:
                        self.session = session
                        selected_model = model_name
                        logger.info('✓ Successfully connected to Gemini Live model: %s', selected_model)
                        break
                except Exception as e:
                    logger.warning('Failed to connect to model %s: %s', model_name, str(e)[:100])
                    continue
            
            if not selected_model:
                raise Exception('All Gemini Live models failed. Check API key and quota.')
            
            logger.debug('RoomGeminiSession started for call_id: %s (model: %s)', self.call_id, selected_model)
                
            async for response in session.receive():
                server_content = getattr(response, 'server_content', None)
                if server_content is not None:
                    model_turn = getattr(server_content, 'model_turn', None)
                    if model_turn is not None:
                        for part in model_turn.parts:
                            if getattr(part, 'inline_data', None) is not None:
                                # Broadcast audio response to all users in this room
                                try:
                                    encoded_audio = base64.b64encode(part.inline_data.data).decode('ascii')
                                    logger.debug('Broadcasting audio chunk from Gemini to call_id: %s (%d bytes)', 
                                              self.call_id, len(encoded_audio))
                                    # Use channel layer to broadcast to all in the room
                                    from channels.layers import get_channel_layer
                                    channel_layer = get_channel_layer()
                                    await channel_layer.group_send(
                                        f'live_call_{self.call_id}',
                                        {
                                            'type': 'room.audio_chunk',
                                            'data': encoded_audio,
                                            'sample_rate': 16000,
                                            'encoding': 'pcm16'
                                        }
                                    )
                                except Exception as broadcast_err:
                                    logger.error('Failed to broadcast audio: %s', broadcast_err)
                    
                    # Handle tool calls (e.g., show_demonstration_card)
                    if getattr(response, 'tool_call', None) is not None:
                        for call in response.tool_call.function_calls:
                            if call.name == 'show_demonstration_card':
                                logger.debug('RoomGeminiSession tool_call: %s', call.name)
                                try:
                                    from channels.layers import get_channel_layer
                                    channel_layer = get_channel_layer()
                                    await channel_layer.group_send(
                                        f'live_call_{self.call_id}',
                                        {
                                            'type': 'room.tool_call',
                                            'name': call.name,
                                            'args': call.args,
                                        }
                                    )
                                    await session.send_tool_response(
                                        types.LiveClientToolResponse(
                                            function_responses=[
                                                types.FunctionResponse(name=call.name, id=call.id, response={'status': 'rendered'})
                                            ]
                                        )
                                    )
                                except Exception as tool_err:
                                    logger.error('Failed to handle tool call: %s', tool_err)
        except asyncio.CancelledError:
            logger.debug('RoomGeminiSession cancelled for call_id: %s', self.call_id)
        except Exception as exc:
            logger.error('RoomGeminiSession error for call_id %s: %s', self.call_id, exc)
            from channels.layers import get_channel_layer
            channel_layer = get_channel_layer()
            await channel_layer.group_send(
                f'live_call_{self.call_id}',
                {
                    'type': 'room.error',
                    'message': str(exc),
                }
            )
        finally:
            self.is_active = False
            self.session = None
    
    async def send_audio(self, audio_bytes):
        """Send audio from a user to Gemini."""
        if self.session and self.is_active:
            try:
                await self.session.send_realtime_input(
                    media_chunks=[types.Blob(data=audio_bytes, mime_type='audio/pcm;rate=16000')]
                )
            except Exception as exc:
                logger.error('Error sending audio to Gemini: %s', exc)
    
    async def send_text(self, text):
        """Send text from a user to Gemini."""
        if self.session and self.is_active:
            try:
                await self.session.send_realtime_input(text=text)
            except Exception as exc:
                logger.error('Error sending text to Gemini: %s', exc)
    
    async def stop(self):
        """Stop the Gemini session."""
        self.is_active = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        if self.session:
            try:
                await self.session.close()
            except:
                pass
        self.session = None

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# WebRTC Configuration (for future LiveKit/Agora integration)
LIVEKIT_URL = os.environ.get('LIVEKIT_URL', '')
LIVEKIT_API_KEY = os.environ.get('LIVEKIT_API_KEY', '')
LIVEKIT_API_SECRET = os.environ.get('LIVEKIT_API_SECRET', '')

class LiveTeacherConsumer(AsyncWebsocketConsumer):
    """
    Consumer for live classroom streaming.
    
    KEY ARCHITECTURAL CHANGES:
    - Each room has ONE shared Gemini session (not one per user)
    - Only the host's audio feeds into Gemini
    - All guests receive Gemini's audio response via broadcast
    - Guests can send text questions that go to the host's Gemini session
    - WebRTC handles video (separate from audio WebSocket)
    """
    
    async def connect(self):
        await self.accept()
        self.user_id = str(uuid.uuid4())
        self.call_id = None
        self.is_host = False
        self.mock_mode = not GENAI_AVAILABLE or types is None
        self.client = None
        
        logger.debug('LiveTeacherConsumer connected: %s (user_id: %s)', self.channel_name, self.user_id)
        
        # Join lobby to see available calls
        await self.channel_layer.group_add(LIVE_LOBBY_GROUP, self.channel_name)
        await self.send_lobby_state()
        
        if self.mock_mode:
            await self.send(text_data=json.dumps({
                'type': 'info',
                'message': 'Live mode fallback enabled. Gemini Live is unavailable, but the lobby is operational.'
            }))
            return
        
        # Initialize Gemini client (for later use when hosting)
        self.client = genai.Client(api_key=GEMINI_API_KEY)
    
    async def send_lobby_state(self):
        await self.send(text_data=json.dumps({
            'type': 'lobby_update',
            'calls': list(ACTIVE_LIVE_CALLS.values())
        }))

    async def broadcast_lobby_state(self):
        await self.channel_layer.group_send(
            LIVE_LOBBY_GROUP,
            {
                'type': 'lobby.update',
                'calls': list(ACTIVE_LIVE_CALLS.values())
            }
        )

    async def lobby_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'lobby_update',
            'calls': event['calls']
        }))

    def get_call_group_name(self, call_id):
        return f'live_call_{call_id}'

    async def join_call_group(self, call_id):
        if not call_id:
            return
        await self.channel_layer.group_add(self.get_call_group_name(call_id), self.channel_name)

    async def leave_call_group(self, call_id):
        if not call_id:
            return
        await self.channel_layer.group_discard(self.get_call_group_name(call_id), self.channel_name)
    
    # Room-level broadcast handlers (for Gemini output and room events)
    async def room_audio_chunk(self, event):
        """Broadcast audio chunk from room's Gemini session to all users."""
        await self.send(text_data=json.dumps({
            'type': 'audio_chunk',
            'data': event['data'],
            'sample_rate': event.get('sample_rate', 16000),
            'encoding': event.get('encoding', 'pcm16'),
        }))
    
    async def room_tool_call(self, event):
        """Broadcast tool calls (e.g., demonstration cards) to all users."""
        await self.send(text_data=json.dumps({
            'type': 'tool_call',
            'name': event['name'],
            'args': event['args'],
        }))
    
    async def room_error(self, event):
        """Broadcast errors to all users in room."""
        await self.send(text_data=json.dumps({
            'type': 'error',
            'message': event['message']
        }))
    
    async def room_state_change(self, event):
        """Broadcast state changes (listening, speaking, thinking) to all users."""
        await self.send(text_data=json.dumps({
            'type': 'state_change',
            'state': event['state']
        }))

    async def call_chat_message(self, event):
        """Broadcast chat messages to all users in room."""
        await self.send(text_data=json.dumps({
            'type': 'chat_message',
            'message': event['message']
        }))
    
    async def call_state_change(self, event):
        """For backward compatibility."""
        await self.room_state_change(event)
    
    async def call_audio_chunk(self, event):
        """For backward compatibility."""
        await self.room_audio_chunk(event)
    
    async def call_tool_call(self, event):
        """For backward compatibility."""
        await self.room_tool_call(event)

    async def receive(self, text_data=None, bytes_data=None):
        logger.debug('LiveTeacherConsumer receive text_data=%s bytes_data=%s',
                     text_data[:200] if text_data else None,
                     len(bytes_data) if bytes_data else None)

        if text_data:
            data = json.loads(text_data)
            message_type = data.get('type')

            if message_type == 'get_lobby':
                await self.send_lobby_state()
                return

            if message_type == 'create_call':
                """Create a new live call and become the host."""
                title = data.get('title', 'Live Study Call').strip() or 'Live Study Call'
                call_id = f'call-{int(time.time() * 1000)}'
                
                ACTIVE_LIVE_CALLS[call_id] = {
                    'id': call_id,
                    'title': title,
                    'host': data.get('host', 'You'),
                    'participants': 1,
                    'topic': data.get('topic', 'Open Study'),
                    'status': 'Live'
                }
                ACTIVE_CALL_MEMBERS[call_id] = {self.user_id}
                
                # Mark this user as the host
                ROOM_HOSTS[call_id] = self.user_id
                
                self.call_id = call_id
                self.is_host = True
                
                await self.join_call_group(call_id)
                
                # Create and start the room's Gemini session (only once)
                if call_id not in ROOM_GEMINI_SESSIONS and not self.mock_mode:
                    config = types.LiveConnectConfig(
                        response_modalities=[types.Modality.AUDIO],
                        system_instruction=types.Content(
                            parts=[types.Part(text='You are Nakintu AI, an expert real-time academic mentor. You speak concisely. When illustrating a structured technical workflow, use the show_demonstration_card tool.')]
                        ),
                        tools=[
                            types.Tool(
                                function_declarations=[
                                    types.FunctionDeclaration(
                                        name='show_demonstration_card',
                                        description='Displays a visual demonstration strip card on the user interface.',
                                        parameters=types.Schema(
                                            type=types.Type.OBJECT,
                                            properties={
                                                'card_type': types.Schema(type=types.Type.STRING, description="Type: 'code' or 'concept'"),
                                                'title': types.Schema(type=types.Type.STRING, description='Title of illustration'),
                                                'content_markdown': types.Schema(type=types.Type.STRING, description='Main explanation in clean markdown syntax'),
                                            },
                                            required=['card_type', 'title', 'content_markdown'],
                                        ),
                                    )
                                ]
                            )
                        ]
                    )
                    room_session = RoomGeminiSession(call_id, self.client, config)
                    ROOM_GEMINI_SESSIONS[call_id] = room_session
                    await room_session.start()
                    logger.debug('Started Gemini session for call_id: %s', call_id)
                
                await self.send(text_data=json.dumps({
                    'type': 'created_call',
                    'call': ACTIVE_LIVE_CALLS[call_id]
                }))
                await self.broadcast_lobby_state()
                return

            if message_type == 'join_call':
                """Join an existing live call as a guest."""
                call_id = data.get('call_id')
                call = ACTIVE_LIVE_CALLS.get(call_id)
                
                if call:
                    # Leave previous call if in one
                    if self.call_id and self.call_id != call_id:
                        await self.leave_call_group(self.call_id)
                    
                    # Join the call
                    members = ACTIVE_CALL_MEMBERS.setdefault(call_id, set())
                    if self.user_id not in members:
                        members.add(self.user_id)
                        call['participants'] = len(members)
                    
                    self.call_id = call_id
                    self.is_host = False  # Joining as guest
                    
                    await self.join_call_group(call_id)
                    await self.send(text_data=json.dumps({
                        'type': 'joined_call',
                        'call': call
                    }))
                    await self.broadcast_lobby_state()
                return

            if message_type == 'chat_message':
                """Send a chat message to the call."""
                if not self.call_id:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Join a live call before sending a chat message.'
                    }))
                    return

                text = (data.get('text') or '').strip()
                if not text:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Cannot send an empty chat message.'
                    }))
                    return

                chat_payload = {
                    'sender': data.get('sender', 'Viewer'),
                    'text': text,
                    'call_id': self.call_id,
                    'timestamp': int(time.time())
                }
                await self.channel_layer.group_send(
                    self.get_call_group_name(self.call_id),
                    {
                        'type': 'call.chat_message',
                        'message': chat_payload
                    }
                )
                return

            if message_type == 'leave_call':
                """Leave the current call."""
                call_id = data.get('call_id') or self.call_id
                await self._leave_current_call(call_id)
                return

            if message_type == 'start_audio':
                """Start sending audio (microphone enabled)."""
                if self.call_id:
                    await self.channel_layer.group_send(
                        self.get_call_group_name(self.call_id),
                        {
                            'type': 'room.state_change',
                            'state': 'listening'
                        }
                    )
                else:
                    await self.send(text_data=json.dumps({'type': 'error', 'message': 'Join a live call before enabling your mic.'}))
                return

            if message_type == 'stop_audio':
                """Stop sending audio."""
                if self.call_id:
                    await self.channel_layer.group_send(
                        self.get_call_group_name(self.call_id),
                        {
                            'type': 'room.state_change',
                            'state': 'idle'
                        }
                    )
                return

            if message_type == 'audio_stream':
                """
                Receive audio from user and send to room's Gemini session.
                
                IMPORTANT: Only the host's audio is forwarded to Gemini.
                Guests' audio is ignored (they can only send text questions).
                """
                if not self.call_id:
                    await self.send(text_data=json.dumps({'type': 'error', 'message': 'Join a live call before sending audio.'}))
                    return
                
                # Only process audio from the host
                if not self.is_host:
                    # Guests cannot send audio directly to Gemini
                    logger.debug('Guest audio ignored (user_id: %s). Use text_question instead.', self.user_id)
                    await self.send(text_data=json.dumps({
                        'type': 'info',
                        'message': 'As a guest, use text questions instead of audio.'
                    }))
                    return
                
                if self.mock_mode:
                    await self.channel_layer.group_send(
                        self.get_call_group_name(self.call_id),
                        {'type': 'room.state_change', 'state': 'speaking'}
                    )
                    asyncio.create_task(self.send_mock_response())
                    return
                
                # Get the room's Gemini session
                room_session = ROOM_GEMINI_SESSIONS.get(self.call_id)
                if room_session is None:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Room Gemini session not ready.'
                    }))
                    return
                
                encoded_chunk = data.get('data')
                if not encoded_chunk:
                    await self.send(text_data=json.dumps({'type': 'error', 'message': 'Missing audio stream payload.'}))
                    return
                
                try:
                    audio_bytes = base64.b64decode(encoded_chunk)
                    logger.debug('Host audio forwarded to Gemini: %s bytes', len(audio_bytes))
                    
                    # Send host audio to the room's shared Gemini session
                    await room_session.send_audio(audio_bytes)
                except Exception as exc:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': f'Failed to forward audio chunk: {exc}',
                    }))
                return

            if message_type == 'text_question':
                """
                Guest sends text question to the host's Gemini session.
                """
                if not self.call_id:
                    await self.send(text_data=json.dumps({'type': 'error', 'message': 'Join a live call first.'}))
                    return
                
                if self.mock_mode:
                    await self.channel_layer.group_send(
                        self.get_call_group_name(self.call_id),
                        {'type': 'room.state_change', 'state': 'thinking'}
                    )
                    asyncio.create_task(self.send_mock_response(data.get('text', '')))
                    return
                
                # Get the room's Gemini session
                room_session = ROOM_GEMINI_SESSIONS.get(self.call_id)
                if room_session is None:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Room Gemini session not ready.'
                    }))
                    return
                
                question_text = data.get('text', '').strip()
                if not question_text:
                    return
                
                logger.debug('Text question forwarded to Gemini: %s', question_text)
                await room_session.send_text(question_text)
                return
            
            if message_type == 'webrtc_token_request':
                """
                Request WebRTC token for video streaming (LiveKit integration).
                """
                if not LIVEKIT_URL or not LIVEKIT_API_KEY:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'WebRTC is not configured on this server.'
                    }))
                    return
                
                call_id = self.call_id or data.get('call_id')
                if not call_id:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'No active call.'
                    }))
                    return
                
                # Generate token (implementation in separate service or helper)
                try:
                    # Import LiveKit token generator
                    from livekit import AccessToken, VideoGrants
                    
                    # Create token for this user in the room
                    token = AccessToken(
                        LIVEKIT_API_KEY,
                        LIVEKIT_API_SECRET,
                        identity=self.user_id,
                        grants=VideoGrants(
                            room_join=True,
                            room=call_id,
                            can_publish=self.is_host,  # Only host can publish video
                            can_publish_data=True,
                        ),
                    )
                    
                    await self.send(text_data=json.dumps({
                        'type': 'webrtc_token',
                        'token': token.to_jwt(),
                        'url': LIVEKIT_URL,
                        'room': call_id,
                    }))
                except ImportError:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'LiveKit SDK not installed.'
                    }))
                except Exception as exc:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': f'Failed to generate WebRTC token: {exc}'
                    }))
                return

        if bytes_data:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Binary frames are no longer supported. Use structured JSON audio_stream events.'
            }))
            return

    async def _leave_current_call(self, call_id):
        """Leave a call and clean up resources."""
        if not call_id:
            return
        
        members = ACTIVE_CALL_MEMBERS.get(call_id, set())
        members.discard(self.user_id)
        
        if members:
            ACTIVE_LIVE_CALLS[call_id]['participants'] = len(members)
            ACTIVE_CALL_MEMBERS[call_id] = members
        else:
            # Last member left, clean up the call and its Gemini session
            ACTIVE_LIVE_CALLS.pop(call_id, None)
            ACTIVE_CALL_MEMBERS.pop(call_id, None)
            ROOM_HOSTS.pop(call_id, None)
            
            # Stop the room's Gemini session
            room_session = ROOM_GEMINI_SESSIONS.pop(call_id, None)
            if room_session:
                await room_session.stop()
                logger.debug('Stopped Gemini session for call_id: %s', call_id)
        
        if self.call_id == call_id:
            self.call_id = None
            self.is_host = False
        
        await self.leave_call_group(call_id)
        await self.broadcast_lobby_state()

    async def send_mock_response(self, question_text=''):
        """Send a mock response for testing (when Gemini is unavailable)."""
        await asyncio.sleep(1)
        if self.call_id:
            await self.channel_layer.group_send(
                self.get_call_group_name(self.call_id),
                {
                    'type': 'room.tool_call',
                    'name': 'show_demonstration_card',
                    'args': {
                        'card_type': 'concept',
                        'title': 'Live Summary',
                        'content_markdown': f'**Quick answer:** Nakintu AI heard your question and is sharing a live summary for *{question_text or "your request"}*.\n\n- Stay focused on the main idea.\n- Ask for examples if you want more clarity.\n- Use the call chat to keep learning together.'
                    }
                }
            )
        await asyncio.sleep(0.5)
        if self.call_id:
            await self.channel_layer.group_send(
                self.get_call_group_name(self.call_id),
                {
                    'type': 'room.state_change',
                    'state': 'ready'
                }
            )

    async def disconnect(self, close_code):
        """Clean up when user disconnects."""
        if self.call_id:
            await self._leave_current_call(self.call_id)
        await self.channel_layer.group_discard(LIVE_LOBBY_GROUP, self.channel_name)
        logger.debug('LiveTeacherConsumer disconnected: %s', self.channel_name)
