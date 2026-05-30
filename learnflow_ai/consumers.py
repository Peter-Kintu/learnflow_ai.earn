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

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

class LiveTeacherConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.client = None
        self.gemini_session = None
        self.live_session_task = None
        self.call_id = None
        self.user_id = str(uuid.uuid4())
        self.mock_mode = not GENAI_AVAILABLE or types is None
        logger.debug('LiveTeacherConsumer connect accepted: %s', self.channel_name)

        await self.channel_layer.group_add(LIVE_LOBBY_GROUP, self.channel_name)
        await self.send_lobby_state()

        if self.mock_mode:
            await self.send(text_data=json.dumps({
                'type': 'info',
                'message': 'Live mode fallback enabled. Gemini Live is unavailable, but the lobby is operational.'
            }))
            self.has_sent_speaking_state = False
            return

        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.config = types.LiveConnectConfig(
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
        self.has_sent_speaking_state = False
        self.live_session_task = asyncio.create_task(self.stream_with_gemini())

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

    async def call_audio_chunk(self, event):
        await self.send(text_data=json.dumps({
            'type': 'audio_chunk',
            'data': event['data'],
            'sample_rate': event.get('sample_rate', 16000),
            'encoding': event.get('encoding', 'pcm16'),
        }))

    async def call_tool_call(self, event):
        await self.send(text_data=json.dumps({
            'type': 'tool_call',
            'name': event['name'],
            'args': event['args'],
        }))

    async def call_state_change(self, event):
        await self.send(text_data=json.dumps({
            'type': 'state_change',
            'state': event['state']
        }))

    async def stream_with_gemini(self):
        try:
            async with self.client.aio.live.connect(model='gemini-3.1-flash-live-preview', config=self.config) as session:
                self.gemini_session = session
                logger.debug('LiveTeacherConsumer live session started: %s', self.channel_name)
                await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'listening'}))

                async for response in session.receive():
                    server_content = getattr(response, 'server_content', None)
                    if server_content is not None:
                        model_turn = getattr(server_content, 'model_turn', None)
                        if model_turn is not None:
                            for part in model_turn.parts:
                                if getattr(part, 'inline_data', None) is not None:
                                    if not self.has_sent_speaking_state:
                                        if self.call_id:
                                            await self.channel_layer.group_send(
                                                self.get_call_group_name(self.call_id),
                                                {
                                                    'type': 'call.state_change',
                                                    'state': 'speaking'
                                                }
                                            )
                                        else:
                                            await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'speaking'}))
                                        self.has_sent_speaking_state = True

                                    encoded_audio = base64.b64encode(part.inline_data.data).decode('ascii')
                                    if self.call_id:
                                        await self.channel_layer.group_send(
                                            self.get_call_group_name(self.call_id),
                                            {
                                                'type': 'call.audio_chunk',
                                                'data': encoded_audio,
                                                'sample_rate': 16000,
                                                'encoding': 'pcm16'
                                            }
                                        )
                                    else:
                                        await self.send(text_data=json.dumps({
                                            'type': 'audio_chunk',
                                            'data': encoded_audio,
                                            'sample_rate': 16000,
                                            'encoding': 'pcm16'
                                        }))

                    if getattr(response, 'tool_call', None) is not None:
                        for call in response.tool_call.function_calls:
                            if call.name == 'show_demonstration_card':
                                logger.debug('LiveTeacherConsumer sending tool_call: %s %s', call.name, call.args)
                                if self.call_id:
                                    await self.channel_layer.group_send(
                                        self.get_call_group_name(self.call_id),
                                        {
                                            'type': 'call.tool_call',
                                            'name': call.name,
                                            'args': call.args,
                                        }
                                    )
                                else:
                                    await self.send(text_data=json.dumps({
                                        'type': 'tool_call',
                                        'name': call.name,
                                        'args': call.args,
                                    }))
                                await session.send_tool_response(
                                    types.LiveClientToolResponse(
                                        function_responses=[
                                            types.FunctionResponse(name=call.name, id=call.id, response={'status': 'rendered'})
                                        ]
                                    )
                                )
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            await self.send(text_data=json.dumps({'type': 'error', 'message': str(exc)}))
        finally:
            await self.close()

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
                self.call_id = call_id
                await self.join_call_group(call_id)
                await self.broadcast_lobby_state()
                return

            if message_type == 'join_call':
                call_id = data.get('call_id')
                call = ACTIVE_LIVE_CALLS.get(call_id)
                if call:
                    if self.call_id and self.call_id != call_id:
                        await self.leave_call_group(self.call_id)
                    members = ACTIVE_CALL_MEMBERS.setdefault(call_id, set())
                    if self.user_id not in members:
                        members.add(self.user_id)
                        call['participants'] = len(members)
                    self.call_id = call_id
                    await self.join_call_group(call_id)
                    await self.broadcast_lobby_state()
                return

            if message_type == 'leave_call':
                call_id = data.get('call_id') or self.call_id
                await self._leave_current_call(call_id)
                return

            if message_type == 'start_audio':
                if self.call_id:
                    await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'listening'}))
                else:
                    await self.send(text_data=json.dumps({'type': 'error', 'message': 'Join a live call before enabling your mic.'}))
                return

            if message_type == 'stop_audio':
                await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'idle'}))
                return

            if message_type == 'audio_stream':
                if not self.call_id:
                    await self.send(text_data=json.dumps({'type': 'error', 'message': 'Join a live call before sending audio.'}))
                    return
                if self.mock_mode:
                    await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'speaking'}))
                    asyncio.create_task(self.send_mock_response())
                    return
                if self.gemini_session is None:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Gemini live session is not ready for audio input yet.'
                    }))
                    return
                source_call_id = data.get('call_id')
                if source_call_id and source_call_id != self.call_id:
                    await self.send(text_data=json.dumps({'type': 'error', 'message': 'Audio stream call_id mismatch.'}))
                    return
                encoded_chunk = data.get('data')
                if not encoded_chunk:
                    await self.send(text_data=json.dumps({'type': 'error', 'message': 'Missing audio stream payload.'}))
                    return
                try:
                    audio_bytes = base64.b64decode(encoded_chunk)
                    logger.debug('LiveTeacherConsumer forwarding audio chunk %s bytes', len(audio_bytes))
                    await self.gemini_session.send_realtime_input(
                        media_chunks=[types.Blob(data=audio_bytes, mime_type='audio/pcm;rate=16000')]
                    )
                except Exception as exc:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': f'Failed to forward audio chunk: {exc}',
                    }))
                return

            if message_type == 'text_question':
                await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'thinking'}))
                if self.mock_mode:
                    asyncio.create_task(self.send_mock_response(data.get('text', '')))
                elif self.gemini_session:
                    await self.gemini_session.send_realtime_input(text=data.get('text'))
                return

        if bytes_data:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Binary frames are no longer supported. Use structured JSON audio_stream events.'
            }))
            return

    async def _leave_current_call(self, call_id):
        if not call_id:
            return
        members = ACTIVE_CALL_MEMBERS.get(call_id, set())
        members.discard(self.user_id)
        if members:
            ACTIVE_LIVE_CALLS[call_id]['participants'] = len(members)
            ACTIVE_CALL_MEMBERS[call_id] = members
        else:
            ACTIVE_LIVE_CALLS.pop(call_id, None)
            ACTIVE_CALL_MEMBERS.pop(call_id, None)
        if self.call_id == call_id:
            self.call_id = None
        await self.leave_call_group(call_id)
        await self.broadcast_lobby_state()

    async def send_mock_response(self, question_text=''):
        await asyncio.sleep(1)
        await self.send(text_data=json.dumps({'type': 'tool_call', 'name': 'show_demonstration_card', 'args': {
            'card_type': 'concept',
            'title': 'Live Summary',
            'content_markdown': f'**Quick answer:** Nakintu AI heard your question and is sharing a live summary for *{question_text or "your request"}*.\n\n- Stay focused on the main idea.\n- Ask for examples if you want more clarity.\n- Use the call chat to keep learning together.'
        }}))
        await asyncio.sleep(0.5)
        await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'ready'}))

    async def disconnect(self, close_code):
        if self.call_id:
            await self._leave_current_call(self.call_id)
        await self.channel_layer.group_discard(LIVE_LOBBY_GROUP, self.channel_name)
        if self.live_session_task:
            self.live_session_task.cancel()
