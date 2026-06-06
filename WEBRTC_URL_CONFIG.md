# URL Configuration for WebRTC and Live Classroom

Add the following to your Django URL configuration to expose the new WebRTC endpoints.

## Step 1: Update `learnflow_ai/urls.py`

Add this import at the top:
```python
from learnflow_ai import webrtc_views
```

Then add these URL patterns:

```python
from django.urls import path, include
from learnflow_ai import webrtc_views

urlpatterns = [
    # ... existing patterns ...
    
    # WebRTC and Live Classroom APIs
    path('api/webrtc/token/', webrtc_views.webrtc_token, name='webrtc_token'),
    path('api/webrtc/config/', webrtc_views.webrtc_config, name='webrtc_config'),
    path('api/csrf-token/', webrtc_views.csrf_token_view, name='csrf_token'),
    
    # ... rest of patterns ...
]
```

## Step 2: Update Django Settings (`learnflow_ai/settings.py`)

Ensure these settings are configured:

### INSTALLED_APPS
```python
INSTALLED_APPS = [
    # ... existing apps ...
    'daphne',  # For WebSocket support
    'channels',
    # ... rest of apps ...
]
```

### ASGI_APPLICATION
```python
ASGI_APPLICATION = 'learnflow_ai.asgi.application'
```

### CHANNEL_LAYERS
```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}
```

Or for development (in-memory):
```python
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
```

### CSRF and Security
```python
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://yourdomain.com',
]

# Allow WebSocket CSRF
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
```

### Logging (for debugging)
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'learnflow_ai': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
```

## Step 3: Environment Variables

Create a `.env` file (or set in your deployment):

```bash
# Gemini API
GEMINI_API_KEY=your-gemini-api-key-here

# WebRTC Provider Configuration
WEBRTC_PROVIDER=livekit  # Options: livekit, agora, janus

# LiveKit Configuration (if using LiveKit)
LIVEKIT_URL=wss://your-livekit-instance.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# Agora Configuration (if using Agora)
AGORA_APP_ID=your-app-id
AGORA_APP_CERTIFICATE=your-certificate

# Janus Configuration (if using Janus)
JANUS_URL=http://janus-server:8088
JANUS_ADMIN_SECRET=your-admin-secret

# Redis (for Channel Layer)
REDIS_URL=redis://localhost:6379/0
```

## Step 4: Install Dependencies

```bash
# For Gemini
pip install google-generativeai

# For WebSockets and Channels
pip install channels channels-redis

# For LiveKit (if using)
pip install livekit-python livekit

# For Agora (if using)
pip install agora-token-builder

# For real-time transcription (optional)
pip install google-cloud-speech
```

## Step 5: Database Migrations (if needed)

```bash
python manage.py migrate
```

## Step 6: Running with WebSocket Support

Instead of `runserver`, use `daphne`:

```bash
# Development
daphne -b 0.0.0.0 -p 8000 learnflow_ai.asgi:application

# Or with auto-reload for development
daphne -b 0.0.0.0 -p 8000 --reload learnflow_ai.asgi:application
```

Or use Gunicorn with Daphne workers:

```bash
gunicorn \
    --worker-class daphne.workers.UnicornWorker \
    --workers 4 \
    --bind 0.0.0.0:8000 \
    learnflow_ai.asgi:application
```

## Step 7: Test the Setup

### Test WebRTC Token Endpoint
```bash
curl -X POST http://localhost:8000/api/webrtc/token/ \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user-123",
    "call_id": "call-456",
    "is_host": true
  }'

# Expected response (LiveKit):
# {
#   "provider": "livekit",
#   "token": "eyJ...",
#   "url": "wss://...",
#   "room": "call-456"
# }
```

### Test WebRTC Config Endpoint
```bash
curl http://localhost:8000/api/webrtc/config/

# Expected response:
# {
#   "provider": "livekit",
#   "features": {...},
#   "limits": {...}
# }
```

### Test WebSocket Connection
Open browser DevTools and connect to WebSocket:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/live-teacher/');
ws.onopen = () => {
    console.log('Connected');
    ws.send(JSON.stringify({ type: 'get_lobby' }));
};
ws.onmessage = (event) => {
    console.log('Received:', JSON.parse(event.data));
};
```

## Troubleshooting

### "Connection refused" when connecting to WebSocket
- Make sure you're using Daphne (not runserver)
- Check that Daphne is running: `ps aux | grep daphne`
- Verify WebSocket URL uses correct protocol (ws:// for HTTP, wss:// for HTTPS)

### "Channel layer not configured"
- Make sure Redis is running: `redis-server`
- Or configure in-memory channel layer if using development
- Check CHANNEL_LAYERS setting in settings.py

### "Gemini API key not found"
- Set GEMINI_API_KEY environment variable
- Check with: `echo $GEMINI_API_KEY`

### CORS errors
- Add to INSTALLED_APPS: `'corsheaders'`
- Add to MIDDLEWARE: `'corsheaders.middleware.CorsMiddleware'`
- Configure CORS_ALLOWED_ORIGINS in settings

### WebRTC token generation fails
- Verify provider SDK is installed
- Check environment variables for provider credentials
- Look for errors in Django logs

## Next Steps

1. **Frontend Integration**: See [WebRTC Frontend Implementation Guide](./WEBRTC_FRONTEND_GUIDE.md)
2. **Testing**: Run integration tests for WebSocket and WebRTC flows
3. **Deployment**: Configure for production with proper SSL/TLS certificates
4. **Monitoring**: Set up logging and monitoring for live sessions
5. **Scaling**: Configure multiple Daphne workers for production load
