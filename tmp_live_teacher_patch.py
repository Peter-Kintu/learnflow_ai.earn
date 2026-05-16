from pathlib import Path
import re

BASE = Path('c:/Users/NIIH/Desktop/learnflow_ai.earn')

# 1) Add Channels / Daphne to settings.py
settings_path = BASE / 'learnflow_ai' / 'settings.py'
text = settings_path.read_text(encoding='utf-8')
if "'channels'," not in text:
    text = text.replace("    'jazzmin',\n", "    'jazzmin',\n    'channels',\n    'daphne',\n")
if 'ASGI_APPLICATION' not in text:
    text = text.replace("WSGI_APPLICATION = 'learnflow_ai.wsgi.application'\n\n# Database", "WSGI_APPLICATION = 'learnflow_ai.wsgi.application'\nASGI_APPLICATION = 'learnflow_ai.asgi.application'\n\n# Database")
if 'CHANNEL_LAYERS' not in text:
    channel_layers = "\n# Channels configuration for async WebSocket routing\nCHANNEL_LAYERS = {\n    'default': {\n        'BACKEND': 'channels.layers.InMemoryChannelLayer',\n    },\n}\n\n"
    if "WSGI_APPLICATION = 'learnflow_ai.wsgi.application'" in text:
        text = text.replace("WSGI_APPLICATION = 'learnflow_ai.wsgi.application'\n", "WSGI_APPLICATION = 'learnflow_ai.wsgi.application'\n" + channel_layers)
    else:
        text += channel_layers
settings_path.write_text(text, encoding='utf-8')

# 2) Update ASGI config
asgi_path = BASE / 'learnflow_ai' / 'asgi.py'
asgi_text = '''import os

from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'learnflow_ai.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter([
            path('ws/live-teacher/', LiveTeacherConsumer.as_asgi()),
        ])
    ),
})
'''
# Use a more robust patch only if asgi.py is not yet the new version
if 'ProtocolTypeRouter' not in asgi_text:
    pass
asgi_path.write_text(asgi_text, encoding='utf-8')

# 3) Create routing.py and consumers.py
routing_path = BASE / 'learnflow_ai' / 'routing.py'
routing_text = '''from django.urls import path

from .consumers import LiveTeacherConsumer

websocket_urlpatterns = [
    path('ws/live-teacher/', LiveTeacherConsumer.as_asgi()),
]
'''
routing_path.write_text(routing_text, encoding='utf-8')

consumers_path = BASE / 'learnflow_ai' / 'consumers.py'
consumers_text = '''import os
import json
import asyncio

from channels.generic.websocket import AsyncWebsocketConsumer
from google import genai
from google.genai import types

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

class LiveTeacherConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.gemini_session = None
        self.live_session_task = None

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
        if text_data:
            data = json.loads(text_data)
            if data.get('type') == 'text_question' and self.gemini_session is not None:
                await self.send(text_data=json.dumps({'type': 'state_change', 'state': 'thinking'}))
                await self.gemini_session.send_realtime_input(text=data.get('text'))

        if bytes_data and self.gemini_session is not None:
            await self.gemini_session.send_realtime_input(
                media_chunks=[types.Blob(data=bytes_data, mime_type='audio/pcm;rate=16000')]
            )

    async def disconnect(self, close_code):
        if self.live_session_task:
            self.live_session_task.cancel()
'''
consumers_path.write_text(consumers_text, encoding='utf-8')

# 4) Update learnflow.html page content
learnflow_path = BASE / 'legalpages' / 'templates' / 'learnflow.html'
learnflow_text = '''{% extends "base.html" %}
{% load static %}

{% block title %}Live AI Teacher - Nakintu AI{% endblock %}

{% block extra_head %}
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css">
    <script src="https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.0.6/purify.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/marked/11.1.1/marked.min.js"></script>
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    colors: {
                        'primary-bg': '#061928',
                        'secondary-bg': '#0D2640',
                        'panel-bg': '#122E56',
                        'surface-glass': 'rgba(15, 23, 42, 0.88)',
                        'accent-cyan': '#00DDEB',
                        'accent-violet': '#8B5CF6',
                        'text-light': '#E2E8F0',
                        'text-muted': '#94A3B8',
                    },
                    boxShadow: {
                        'soft-glow': '0 20px 60px rgba(0, 221, 235, 0.18)',
                        'outer-glow': '0 28px 90px rgba(15, 23, 42, 0.16)',
                    },
                },
            },
        }
    </script>
    <style>
        body {
            background: radial-gradient(circle at top left, rgba(0, 221, 235, 0.12), transparent 24%),
                        radial-gradient(circle at bottom right, rgba(139, 92, 246, 0.12), transparent 22%),
                        linear-gradient(180deg, #061928 0%, #071B2B 100%);
        }

        .glass-panel {
            background: rgba(13, 38, 64, 0.88);
            backdrop-filter: blur(18px);
            -webkit-backdrop-filter: blur(18px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.35);
        }

        .pulse-ring {
            box-shadow: 0 0 0 rgba(0, 221, 235, 0.5);
            animation: pulseRing 2.5s infinite;
        }

        @keyframes pulseRing {
            0% { transform: scale(0.95); opacity: 0.8; }
            50% { transform: scale(1.06); opacity: 0.3; }
            100% { transform: scale(0.95); opacity: 0.8; }
        }

        .strip-card {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(0, 221, 235, 0.16);
        }

        .canvas-container {
            position: relative;
            overflow: hidden;
            border-radius: 2rem;
        }

        #liveAiCanvas {
            width: 100%;
            height: 100%;
            display: block;
        }

        .state-pill {
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
        }
    </style>
{% endblock %}

{% block content %}
    <div class="min-h-screen px-4 py-10 lg:px-8 lg:py-14 text-text-light">
        <div class="max-w-7xl mx-auto space-y-10">
            <section class="glass-panel p-8 lg:p-12 rounded-[2rem] border border-white/10">
                <div class="grid gap-8 lg:grid-cols-[1.2fr,0.8fr] items-center">
                    <div>
                        <p class="text-sm uppercase tracking-[0.4em] text-accent-cyan mb-4">Live AI Teacher</p>
                        <h1 class="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white mb-6">
                            Build the most responsive real-time Nakintu AI teacher in the world.
                        </h1>
                        <p class="max-w-2xl text-base sm:text-lg text-text-muted leading-8">
                            This page streams browser audio into an async Django Channels backend, proxies it through Gemini Live, and renders structured demonstration cards instantly with Tailwind visuals.
                        </p>
                    </div>
                    <div class="space-y-4 rounded-[1.5rem] bg-secondary-bg/90 p-6 border border-accent-cyan/20 shadow-soft-glow">
                        <div class="inline-flex items-center gap-3 text-sm text-text-muted uppercase tracking-[0.3em] mb-4">
                            <span class="inline-flex h-2.5 w-2.5 rounded-full bg-gradient-to-r from-accent-cyan to-accent-violet pulse-ring"></span>
                            Real-time WebSocket learning channel
                        </div>
                        <div class="rounded-3xl bg-[#071B2F] p-5 border border-white/10">
                            <p class="text-sm text-text-light/80 leading-7">Uses Django Channels + Daphne to keep your backend non-blocking while Gemini Live handles low latency audio and stateful instruction routing.</p>
                        </div>
                        <div class="grid gap-3">
                            <div class="rounded-3xl bg-[#081C31] p-4 border border-accent-cyan/10">
                                <p class="text-sm text-text-muted">Backend Engine</p>
                                <p class="mt-2 text-white font-semibold">Django Channels + Gemini Live</p>
                            </div>
                            <div class="rounded-3xl bg-[#081C31] p-4 border border-accent-cyan/10">
                                <p class="text-sm text-text-muted">Client Experience</p>
                                <p class="mt-2 text-white font-semibold">Canvas pulse + voice input + demo cards</p>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <section class="glass-panel rounded-[2rem] border border-white/10 p-6 lg:p-8">
                <div class="grid gap-6 lg:grid-cols-[1.2fr,0.8fr]">
                    <div class="canvas-container aspect-[16/9] bg-[#061C33] rounded-[2rem] border border-white/10 overflow-hidden">
                        <canvas id="liveAiCanvas"></canvas>
                        <div class="absolute top-5 left-5 inline-flex items-center gap-2 state-pill rounded-full border border-accent-cyan/20 bg-white/10 px-3 py-2 text-xs text-text-light shadow-glow-cyan">
                            <span id="stateDot" class="h-2.5 w-2.5 rounded-full bg-gray-500 animate-pulse"></span>
                            <span id="stateText" class="font-semibold uppercase tracking-[0.25em]">Disconnected</span>
                        </div>
                    </div>

                    <div class="space-y-5">
                        <div class="rounded-[1.75rem] bg-secondary-bg p-6 border border-accent-cyan/15 shadow-soft-glow">
                            <h2 class="text-2xl font-bold text-white mb-3">Live Teaching Controls</h2>
                            <p class="text-text-muted leading-7 mb-6">Tap the microphone button to start your real-time session. Gemini streams audio and delivers rich demonstration cards for every answer.</p>
                            <button id="micBtn" class="w-full inline-flex items-center justify-center gap-3 rounded-2xl bg-gradient-to-r from-accent-cyan to-accent-violet px-6 py-4 text-base font-semibold text-slate-950 shadow-glow-cyan transition duration-200 hover:opacity-95">
                                <i class="fas fa-microphone"></i> Start Speaking
                            </button>
                            <div class="rounded-2xl bg-[#071B2F] p-5 border border-white/10">
                                <p class="text-sm text-text-muted">Current mode:</p>
                                <p class="mt-2 text-white font-semibold" id="modeDescription">Ready for live interaction.</p>
                            </div>
                        </div>

                        <div class="rounded-[1.75rem] bg-secondary-bg p-6 border border-accent-cyan/15 shadow-soft-glow">
                            <h3 class="text-xl font-semibold text-white mb-4">Demonstration Cards</h3>
                            <div id="demonstration-container" class="space-y-4"></div>
                            <p class="text-sm text-text-muted mt-4">Structured cards from Gemini appear here when the model invokes the live tool call.</p>
                        </div>
                    </div>
                </div>
            </section>
        </div>
    </div>
{% endblock %}

{% block extra_js %}
    <script>
        let socket;
        let audioContext;
        let analyserNode;
        let dataArray;
        let aiState = 'idle';
        let micStream;
        let audioProcessor;

        const canvas = document.getElementById('liveAiCanvas');
        const ctx = canvas.getContext('2d');
        const stateDot = document.getElementById('stateDot');
        const stateText = document.getElementById('stateText');
        const micBtn = document.getElementById('micBtn');
        const modeDescription = document.getElementById('modeDescription');

        function initCanvasSize() {
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width = rect.width * window.devicePixelRatio;
            canvas.height = rect.height * window.devicePixelRatio;
            ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
        }

        window.addEventListener('resize', initCanvasSize);
        initCanvasSize();

        function transitionState(newState) {
            aiState = newState;
            stateText.innerText = newState;
            stateDot.className = 'h-2.5 w-2.5 rounded-full animate-pulse';

            modeDescription.textContent = {
                listening: 'Listening for your question...',
                thinking: 'Gemini Live is composing an answer...',
                speaking: 'Nakintu AI is speaking back to you.',
                idle: 'Ready for live interaction.',
            }[newState] || 'Ready for live interaction.';

            if (newState === 'listening') {
                stateDot.classList.add('bg-emerald-400');
            } else if (newState === 'thinking') {
                stateDot.classList.add('bg-violet-500');
            } else if (newState === 'speaking') {
                stateDot.classList.add('bg-accent-cyan');
            } else {
                stateDot.classList.add('bg-gray-500');
            }
        }

        function convertFloat32ToInt16(buffer) {
            const l = buffer.length;
            const buf = new ArrayBuffer(l * 2);
            const view = new DataView(buf);
            let offset = 0;
            for (let i = 0; i < l; i++, offset += 2) {
                let s = Math.max(-1, Math.min(1, buffer[i]));
                view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
            }
            return buf;
        }

        async function startLiveSession() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                alert('Your browser does not support microphone input for live AI sessions.');
                return;
            }

            if (!audioContext) {
                audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
            }
            await audioContext.resume();

            analyserNode = audioContext.createAnalyser();
            analyserNode.fftSize = 256;
            dataArray = new Uint8Array(analyserNode.frequencyBinCount);

            const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
            socket = new WebSocket(`${protocol}://${window.location.host}/ws/live-teacher/`);
            socket.binaryType = 'arraybuffer';

            socket.onopen = async () => {
                transitionState('listening');
                micBtn.disabled = true;
                micBtn.innerHTML = '<i class="fas fa-circle-notch animate-spin"></i> Live Session Active';

                micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const source = audioContext.createMediaStreamSource(micStream);

                audioProcessor = audioContext.createScriptProcessor(4096, 1, 1);
                source.connect(audioProcessor);
                audioProcessor.connect(audioContext.destination);

                audioProcessor.onaudioprocess = (e) => {
                    if (aiState !== 'listening') return;
                    const inputData = e.inputBuffer.getChannelData(0);
                    const int16Buffer = convertFloat32ToInt16(inputData);
                    if (socket && socket.readyState === WebSocket.OPEN) {
                        socket.send(int16Buffer);
                    }
                };
            };

            socket.onmessage = async (event) => {
                if (typeof event.data === 'string') {
                    const payload = JSON.parse(event.data);
                    if (payload.type === 'state_change') {
                        transitionState(payload.state);
                    }
                    if (payload.type === 'tool_call' && payload.name === 'show_demonstration_card') {
                        injectStripCard(payload.args);
                    }
                    return;
                }

                if (event.data instanceof ArrayBuffer) {
                    transitionState('speaking');
                    try {
                        const buffer = await audioContext.decodeAudioData(event.data.slice(0));
                        const sourceNode = audioContext.createBufferSource();
                        sourceNode.buffer = buffer;
                        sourceNode.connect(analyserNode);
                        analyserNode.connect(audioContext.destination);
                        sourceNode.start();
                        sourceNode.onended = () => {
                            transitionState('listening');
                        };
                    } catch (err) {
                        console.warn('Audio decode failed, raw PCM not currently supported by decodeAudioData', err);
                    }
                }
            };

            socket.onerror = () => {
                transitionState('idle');
                micBtn.disabled = false;
                micBtn.innerHTML = '<i class="fas fa-microphone"></i> Start Speaking';
            };

            socket.onclose = () => {
                transitionState('idle');
                micBtn.disabled = false;
                micBtn.innerHTML = '<i class="fas fa-microphone"></i> Start Speaking';
            };
        }

        function injectStripCard(args) {
            const container = document.getElementById('demonstration-container');
            const icon = args.card_type === 'code' ? 'fa-code' : 'fa-lightbulb';
            const cleanHTML = DOMPurify.sanitize(marked.parse(args.content_markdown));
            const cardMarkup = `
                <div class="strip-card flex flex-col gap-4 rounded-3xl border p-5 text-text-light shadow-soft-glow transition duration-300 hover:-translate-y-1">
                    <div class="flex items-center gap-3">
                        <div class="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-cyan/10 text-accent-cyan text-lg">
                            <i class="fas ${icon}"></i>
                        </div>
                        <div>
                            <p class="text-sm uppercase tracking-[0.25em] text-text-muted">Live Demonstration</p>
                            <h3 class="text-lg font-bold text-white">${args.title}</h3>
                        </div>
                    </div>
                    <div class="prose prose-invert max-w-none text-text-muted">${cleanHTML}</div>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', cardMarkup);
        }

        animatePulse();

        let wavePhase = 0;
        function animatePulse() {
            requestAnimationFrame(animatePulse);
            const rect = canvas.parentElement.getBoundingClientRect();
            const w = rect.width;
            const h = rect.height;
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = 'rgba(6, 25, 40, 0.2)';
            ctx.fillRect(0, 0, w, h);

            let amplitude = 12;
            let frequency = 0.015;
            let color = '#00DDEB';

            if (aiState === 'thinking') {
                amplitude = 24;
                frequency = 0.05;
                color = '#8B5CF6';
            } else if (aiState === 'speaking') {
                amplitude = 32;
                frequency = 0.02;
                color = '#00DDEB';
            } else if (aiState === 'listening') {
                amplitude = 16;
                frequency = 0.018;
                color = '#4ADE80';
            }

            wavePhase += 0.05;
            for (let layer = 0; layer < 3; layer++) {
                ctx.beginPath();
                ctx.strokeStyle = layer === 0 ? color : `${color}33`;
                ctx.lineWidth = layer === 0 ? 3 : 1.5;
                for (let x = 0; x <= w; x += 20) {
                    const envelope = Math.sin((x / w) * Math.PI);
                    const y = h / 2 + Math.sin((x * frequency) + wavePhase + layer) * amplitude * envelope;
                    if (x === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }
                ctx.stroke();
            }
        }

        micBtn.addEventListener('click', () => {
            micBtn.disabled = true;
            micBtn.innerHTML = '<i class="fas fa-circle-notch animate-spin"></i> Connecting...';
            startLiveSession();
        });
    </script>
{% endblock %}
'''
learnflow_path.write_text(learnflow_text, encoding='utf-8')

# 5) Add Channels packages to requirements.txt if needed
req_path = BASE / 'requirements.txt'
req_text = req_path.read_text(encoding='utf-16')
if 'channels==' not in req_text:
    req_text = req_text.rstrip() + '\nchannels==4.1.0\n'
if 'daphne==' not in req_text:
    req_text = req_text.rstrip() + '\ndaphne==4.0.0\n'
req_path.write_text(req_text, encoding='utf-16')

print('patch complete')
