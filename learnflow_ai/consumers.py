import os
import json
import asyncio

from channels.generic.websocket import AsyncWebsocketConsumer

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

        if not GENAI_AVAILABLE or types is None:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Gemini Live library not installed. Install google-genai to use live mode.'
            }))
            await self.close()
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

        self.live_session_task = asyncio.create_task(self.stream_with_gemini())

    async def stream_with_gemini(self):
        try:
            async with self.client.aio.live.connect(model='gemini-3.1-flash-live-preview', config=self.config) as session:
                self.gemini_session = session
                await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'listening'}))

                async for response in session.receive():
                    server_content = getattr(response, 'server_content', None)
                    if server_content is not None:
                        model_turn = getattr(server_content, 'model_turn', None)
                        if model_turn is not None:
                            for part in model_turn.parts:
                                if getattr(part, 'inline_data', None) is not None:
                                    await self.send(bytes_data=part.inline_data.data)

                    if getattr(response, 'tool_call', None) is not None:
                        for call in response.tool_call.function_calls:
                            if call.name == 'show_demonstration_card':
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
        if not GENAI_AVAILABLE or self.gemini_session is None:
            return

        if text_data:
            data = json.loads(text_data)
            if data.get('type') == 'text_question':
                await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'thinking'}))
                await self.gemini_session.send_realtime_input(text=data.get('text'))

        if bytes_data:
            await self.gemini_session.send_realtime_input(
                media_chunks=[types.Blob(data=bytes_data, mime_type='audio/pcm;rate=16000')]
            )

    async def disconnect(self, close_code):
        if self.live_session_task:
            self.live_session_task.cancel()
