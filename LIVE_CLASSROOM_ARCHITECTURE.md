# Live Classroom Architecture - Room-Level Gemini Sessions

## Overview

The LearnFlow Live Classroom has been refactored to fix the "echo broadcast" bug where multiple users' individual Gemini instances would respond simultaneously, creating overlapping audio streams. This document describes the new architecture.

## Problem Statement

### Before (Old Architecture)
- **Per-user Gemini sessions**: Each user connecting to a call would create their own independent Gemini Live session
- **Echo broadcasts**: When multiple users were in a room, each user's Gemini instance would respond, causing overlapping audio
- **Inefficient**: Multiple Gemini sessions consuming quota and resources unnecessarily
- **Poor UX**: Viewers heard competing AI voices

### After (New Architecture)
- **Per-room Gemini sessions**: ONE shared Gemini session per room/call, not per user
- **Clean audio**: Only one AI voice responding at a time
- **Host-based control**: Only the host (teacher) can send audio to Gemini
- **Efficient**: Single Gemini session per room saves quota and resources
- **Professional UX**: TikTok-like experience with single authoritative AI mentor

---

## Architecture Diagram

```
Live Classroom Room
├─ Host (Teacher)
│  └─ Audio Input → [Room Gemini Session] → Audio Output
│
├─ Guest 1 (Student)
│  ├─ Receives Audio from Room Gemini
│  ├─ Can send Text Questions → Room Gemini
│  └─ Cannot send raw audio (would create echo)
│
├─ Guest 2 (Student)
│  └─ Same as Guest 1
│
└─ Guest N (Student)
   └─ Same as Guest 1

All Audio/Tool Outputs broadcast via Channel Layer
All Video via WebRTC (LiveKit/Agora/Janus SFU)
```

---

## Key Changes to `consumers.py`

### 1. Room-Level Session Management

**New Global Structures:**
```python
ROOM_GEMINI_SESSIONS = {}   # call_id → RoomGeminiSession
ROOM_HOSTS = {}             # call_id → host_user_id
```

**RoomGeminiSession Class:**
- Wraps a single Gemini Live connection for a room
- Methods:
  - `async start()`: Initialize the Gemini stream
  - `async send_audio(audio_bytes)`: Send host audio to Gemini
  - `async send_text(text)`: Send guest questions to Gemini
  - `async stop()`: Clean up when last user leaves

### 2. Host vs Guest Roles

**On `create_call`:**
- User becomes **host** (`self.is_host = True`)
- Room Gemini session is created
- Only host's audio feeds into Gemini

**On `join_call`:**
- User becomes **guest** (`self.is_host = False`)
- Subscribes to room's existing Gemini session
- Audio is rejected; text questions are forwarded to Gemini

### 3. Audio Routing

**Host Audio Path:**
```
Host WebSocket → audio_stream message
    ↓
LiveTeacherConsumer.receive()
    ↓
room_session.send_audio(decoded_audio_bytes)
    ↓
RoomGeminiSession → Gemini API
    ↓
Gemini audio response
    ↓
channel_layer.group_send('room.audio_chunk')
    ↓
Broadcast to ALL users in room
```

**Guest Text Path:**
```
Guest WebSocket → text_question message
    ↓
LiveTeacherConsumer.receive()
    ↓
room_session.send_text(question_text)
    ↓
RoomGeminiSession → Gemini API
    ↓
Gemini response
    ↓
channel_layer.group_send()
    ↓
Broadcast to ALL users in room
```

### 4. Broadcast Handlers

New channel layer message types (broadcast to all room users):

```python
# When Gemini produces audio
await channel_layer.group_send('live_call_{call_id}', {
    'type': 'room.audio_chunk',
    'data': base64_encoded_pcm16,
    'sample_rate': 16000,
    'encoding': 'pcm16'
})

# When Gemini uses a tool
await channel_layer.group_send('live_call_{call_id}', {
    'type': 'room.tool_call',
    'name': 'show_demonstration_card',
    'args': {...}
})

# When Gemini state changes
await channel_layer.group_send('live_call_{call_id}', {
    'type': 'room.state_change',
    'state': 'listening|speaking|thinking|ready'
})

# On error
await channel_layer.group_send('live_call_{call_id}', {
    'type': 'room.error',
    'message': 'error text'
})
```

### 5. Cleanup on Disconnect

When the last user leaves a room:
1. Room members set becomes empty
2. Room Gemini session is stopped (`await room_session.stop()`)
3. Session removed from `ROOM_GEMINI_SESSIONS`
4. Call removed from `ACTIVE_LIVE_CALLS`
5. Host mapping removed from `ROOM_HOSTS`

---

## WebRTC Integration (Video Streaming)

### Why Separate WebRTC?
- **WebSockets**: Low-latency audio (Gemini responses via PCM16)
- **WebRTC**: Optimized peer-to-peer video
- **Benefits**: Reduces bandwidth, improves video quality, separates concerns

### Supported Providers

#### 1. LiveKit (Recommended)
- **SFU Model**: Selective Forwarding Unit (efficient bandwidth)
- **Features**: Recording, compositing, analytics
- **Setup**: See `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` env vars

#### 2. Agora
- **SFU Model**: Similar to LiveKit
- **Setup**: See `AGORA_APP_ID`, `AGORA_APP_CERTIFICATE` env vars

#### 3. Janus
- **Gateway Model**: More control, lower-level
- **Setup**: See `JANUS_URL`, `JANUS_ADMIN_SECRET` env vars

### Token Generation Endpoint

**POST `/api/webrtc/token/`**

Request:
```json
{
  "user_id": "user-12345",
  "call_id": "call-1234567890",
  "is_host": true
}
```

Response (LiveKit):
```json
{
  "provider": "livekit",
  "token": "eyJ...",
  "url": "wss://live.example.com",
  "room": "call-1234567890"
}
```

### WebSocket Message: `webrtc_token_request`

Clients can request token directly via WebSocket:

```javascript
// In learnflow.html
socket.send(JSON.stringify({
    type: 'webrtc_token_request',
    call_id: activeCallId,
    is_host: isHostUser
}));

// Response with token
socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === 'webrtc_token') {
        // Initialize LiveKit client with token
        // Token in payload.token
        // URL in payload.url
        // Room in payload.room
    }
};
```

---

## Message Flow Examples

### Example 1: Host Speaks (Guest Listens)

```
Host            Channel Layer        Guest       Browser
 │                   │                  │            │
 │─ audio_stream ───>│                  │            │
 │                   │─ room.audio_chunk─────────> AudioContext
 │                   │                              (plays audio)
 │                   │                  │            │
 │  send_audio()     │
 │      ↓            │
 │   Gemini ────────>│
 │      ↓            │
 │   response audio  │
 │      ↓            │
 │   encode B64      │
 │      ↓            │
 │   group_send() ──>│─ room.audio_chunk─────────> AudioContext
 │                   │
```

### Example 2: Guest Asks Question

```
Guest           Channel Layer        Host      Browser
 │                   │                  │            │
 │─ text_question ──>│                  │            │
 │                   │                  │            │
 │   (forwarded to room session)        │            │
 │      ↓            │                  │            │
 │   Gemini ────────>│                  │            │
 │      ↓            │                  │            │
 │   response audio  │                  │            │
 │      ↓            │                  │            │
 │   encode B64      │                  │            │
 │      ↓            │                  │            │
 │   group_send() ──>│─ room.audio_chunk──────────> AudioContext
 │                   │                              (plays answer)
```

---

## Configuration

### Environment Variables

```bash
# Gemini API
GEMINI_API_KEY=your-key-here

# WebRTC Provider (one of: livekit, agora, janus)
WEBRTC_PROVIDER=livekit

# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-livekit-key
LIVEKIT_API_SECRET=your-livekit-secret

# Agora Configuration
AGORA_APP_ID=your-app-id
AGORA_APP_CERTIFICATE=your-certificate

# Janus Configuration
JANUS_URL=http://your-janus-server:8088
JANUS_ADMIN_SECRET=your-admin-secret
```

---

## Frontend Changes Required

### learnflow.html Updates

1. **Handle `room.audio_chunk` broadcasts**:
```javascript
socket.onmessage = (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === 'audio_chunk') {
        playAudioChunk(payload.data);  // Existing function
    }
};
```

2. **Request WebRTC token on call join**:
```javascript
socket.send(JSON.stringify({
    type: 'webrtc_token_request',
    call_id: activeCallId
}));
```

3. **Initialize LiveKit client**:
```javascript
if (payload.type === 'webrtc_token') {
    const { LiveClient } = window;
    const room = new LiveClient.Room();
    await room.connect(payload.url, payload.token);
    room.localParticipant.videoTrackSubscriptions.forEach(track => {
        // Handle local video
    });
    room.participants.forEach(participant => {
        // Handle remote video
    });
}
```

---

## Migration from Old Code

### Breaking Changes

1. **No more `stream_with_gemini()` method per user**
   - Gemini session now managed by `RoomGeminiSession`
   - Each consumer no longer has `self.gemini_session`

2. **`self.is_host` flag replaces logic**
   - Only hosts can send audio to Gemini
   - Guests send text questions instead

3. **New broadcast message types**
   - `room.audio_chunk` instead of `call.audio_chunk`
   - `room.tool_call` instead of `call.tool_call`
   - `room.state_change` instead of `call.state_change`
   - Old handlers kept for backward compatibility

### Backward Compatibility

The old `call.*` message types are still supported via proxy handlers:
```python
async def call_audio_chunk(self, event):
    await self.room_audio_chunk(event)
```

---

## Testing

### Test Scenarios

1. **Host Creates Call and Speaks**
   - ✓ Only one Gemini session created
   - ✓ Audio broadcast to guests
   - ✓ No echo or overlapping responses

2. **Multiple Guests Join**
   - ✓ All guests receive same audio
   - ✓ Guests can ask text questions
   - ✓ Gemini responds to guests' questions
   - ✓ All users hear same response

3. **Host Leaves**
   - ✓ Gemini session stops
   - ✓ Call is cleaned up
   - ✓ Guests see error or disconnect

4. **WebRTC Token Generation**
   - ✓ Host gets publisher token
   - ✓ Guests get subscriber token
   - ✓ Token expires after 1 hour
   - ✓ Can request new token before expiry

---

## Performance Considerations

### Bandwidth Savings
- **Before**: N Gemini sessions × bandwidth per session
- **After**: 1 Gemini session per room
- **Savings**: ~90% for typical 10-person classroom

### Latency
- Audio streaming: ~200-500ms (Gemini API latency)
- WebSocket broadcast: ~50-100ms
- WebRTC video: ~100-300ms (peer-to-peer optimized)

### Scalability
- **Per room**: 1 Gemini session, unlimited guests
- **Max rooms**: Limited by Gemini quota (usually 100+ concurrent)
- **Typical**: Easily supports 100+ simultaneous live classrooms

---

## Troubleshooting

### "Echo broadcast" Still Happening
- Check that `is_host` is correctly set
- Verify old listeners aren't responding to both `call.audio_chunk` and `room.audio_chunk`
- Check browser console for multiple audio playback events

### Gemini Session Not Starting
- Verify `GEMINI_API_KEY` is set correctly
- Check `google-generativeai` package is installed
- Look for errors in Django/Daphne logs

### WebRTC Token Generation Fails
- Verify WebRTC provider environment variables
- Check that token generator SDK is installed (`pip install livekit-python`)
- Verify network connectivity to provider service

### Audio Not Playing
- Check that Web Audio API context is created
- Verify `audioContext.state === 'running'`
- Check browser console for audio playback errors
- Verify PCM16 decoding is working

---

## Future Enhancements

1. **Screen Sharing**: Extend WebRTC to include screen share channel
2. **Recording**: Use LiveKit API to record classroom sessions
3. **Transcription**: Convert Gemini audio responses to text for accessibility
4. **Chat Message Moderation**: Filter guest questions before sending to Gemini
5. **Analytics**: Track engagement metrics, question frequency, response quality
6. **Breakout Rooms**: Create sub-rooms with separate Gemini sessions

---

## References

- [Gemini Live API Docs](https://ai.google.dev/gemini-api/docs/live)
- [LiveKit Documentation](https://docs.livekit.io)
- [Agora Documentation](https://docs.agora.io/en/)
- [Janus WebRTC Gateway](https://janus.conf.meetecho.com/)
- [WebSocket Channel Layer (Django Channels)](https://channels.readthedocs.io/)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
