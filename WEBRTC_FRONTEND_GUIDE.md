# WebRTC Frontend Implementation Guide

This guide explains how to implement WebRTC video streaming with LiveKit (or Agora/Janus) in your `learnflow.html` frontend.

## Overview

The frontend now:
1. **Receives audio via WebSocket**: PCM16-encoded Gemini responses from backend
2. **Sends video via WebRTC**: Peer-to-peer or through SFU service
3. **Handles both as separate concerns**: Audio ← WebSocket, Video ← WebRTC

---

## Part 1: Audio Streaming (Already Implemented)

Your existing `learnflow.html` already has:
- ✅ Web Audio API context (16kHz sample rate)
- ✅ PCM16 decoding (`decodePCM16()`)
- ✅ Audio queue management (`audioQueue`, `isPlayingAudio`)
- ✅ Audio playback (`processAudioQueue()`)
- ✅ WebSocket `audio_chunk` handler

**No changes needed for audio streaming!**

---

## Part 2: WebRTC Video Streaming (LiveKit Integration)

### Step 1: Add LiveKit SDK to HTML

Add this to your `learnflow.html` `<head>`:

```html
<!-- LiveKit WebRTC Library -->
<script src="https://cdn.jsdelivr.net/npm/livekit-client@0.11.1/dist/livekit.umd.js"></script>

<!-- Or for ES modules (preferred) -->
<script type="importmap">
{
  "imports": {
    "livekit-client": "https://cdn.jsdelivr.net/npm/livekit-client@0.11.1/dist/index.es.mjs"
  }
}
</script>
```

Or install locally:
```bash
npm install livekit-client
```

### Step 2: Add WebRTC Variables (in `learnflow.html` script)

Add these near the top of your existing JavaScript:

```javascript
// WebRTC (Video Streaming)
let liveKitRoom = null;
let localVideoElement = null;
let remoteVideoElements = {};  // participant_id -> video_element
let isVideoEnabled = false;
let videoStartTime = null;

// WebRTC Configuration (will be populated from server)
let webrtcConfig = null;
```

### Step 3: Request WebRTC Configuration

When page loads, request WebRTC config:

```javascript
async function loadWebRTCConfig() {
    try {
        const response = await fetch('/api/webrtc/config/');
        const config = await response.json();
        webrtcConfig = config;
        console.log('WebRTC Config:', webrtcConfig);
        
        // Show supported features
        const features = config.features;
        console.log(`WebRTC Provider: ${config.provider}`);
        console.log(`Capabilities: Video=${features.video}, Audio=${features.audio}, Screen Share=${features.screen_share}`);
    } catch (error) {
        console.error('Failed to load WebRTC config:', error);
    }
}

// Call on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadWebRTCConfig();
    // ... rest of initialization
});
```

### Step 4: Request WebRTC Token

When joining a call, request a token from the backend:

```javascript
async function requestWebRTCToken(callId, isHost) {
    try {
        const response = await fetch('/api/webrtc/token/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken') || document.querySelector('[name=csrfmiddlewaretoken]')?.value || ''
            },
            body: JSON.stringify({
                user_id: userIdGlobal,  // Your user ID variable
                call_id: callId,
                is_host: isHost
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to get token');
        }
        
        const tokenData = await response.json();
        console.log('WebRTC Token received:', tokenData.provider);
        return tokenData;
    } catch (error) {
        console.error('Failed to request WebRTC token:', error);
        showToast(`Video setup failed: ${error.message}`);
        return null;
    }
}

// Helper to get CSRF token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
```

### Step 5: Initialize LiveKit Room

```javascript
async function connectToLiveKit(tokenData) {
    try {
        const { default: LiveClient } = await import('livekit-client');
        
        // Create room
        liveKitRoom = new LiveClient.Room({
            video: { width: 640 },
            audio: true,
            autoSubscribe: true,
        });
        
        // Handle local participant
        liveKitRoom.localParticipant.on(LiveClient.ParticipantEvent.TrackSubscribed, (track) => {
            console.log(`Track subscribed:`, track.kind);
            if (track.kind === 'video') {
                const videoElement = createRemoteVideoElement(liveKitRoom.localParticipant.identity);
                liveKitRoom.localParticipant.videoTrackSubscriptions.forEach(subscription => {
                    const mediaStreamTrack = subscription.mediaStreamTrack;
                    if (mediaStreamTrack) {
                        const stream = new MediaStream([mediaStreamTrack]);
                        videoElement.srcObject = stream;
                        videoElement.play().catch(e => console.error('Play failed:', e));
                    }
                });
            }
        });
        
        // Handle remote participants
        liveKitRoom.on(LiveClient.RoomEvent.ParticipantConnected, (participant) => {
            console.log(`Participant connected: ${participant.identity}`);
            subscribeToParticipant(participant);
        });
        
        liveKitRoom.on(LiveClient.RoomEvent.ParticipantDisconnected, (participant) => {
            console.log(`Participant disconnected: ${participant.identity}`);
            removeRemoteVideoElement(participant.identity);
        });
        
        // Handle room disconnection
        liveKitRoom.on(LiveClient.RoomEvent.Disconnected, () => {
            console.log('Disconnected from LiveKit room');
            cleanupVideoElements();
        });
        
        // Connect to room
        await liveKitRoom.connect(tokenData.url, tokenData.token, {
            autoSubscribe: true,
            maxRetries: 3,
            reconnectFallbackMs: 5000,
        });
        
        console.log('Connected to LiveKit room:', tokenData.room);
        isVideoEnabled = true;
        videoStartTime = Date.now();
        
        // Publish local video if host
        if (tokenData.is_host || true) {  // For now, all can publish
            try {
                await liveKitRoom.localParticipant.enableCameraAndMicrophone();
                console.log('Camera and microphone enabled');
            } catch (error) {
                console.warn('Could not enable camera/microphone:', error);
            }
        }
        
        return true;
    } catch (error) {
        console.error('Failed to connect to LiveKit:', error);
        isVideoEnabled = false;
        showToast(`Video connection failed: ${error.message}`);
        return false;
    }
}

// Subscribe to participant's tracks
function subscribeToParticipant(participant) {
    participant.on(LiveClient.ParticipantEvent.TrackSubscribed, (track) => {
        console.log(`Track subscribed from ${participant.identity}:`, track.kind);
        
        if (track.kind === 'video') {
            const videoElement = createRemoteVideoElement(participant.identity);
            const stream = new MediaStream([track.mediaStreamTrack]);
            videoElement.srcObject = stream;
            videoElement.play().catch(e => console.error('Play failed:', e));
        } else if (track.kind === 'audio') {
            // Audio handled by LiveKit automatically
            console.log('Audio track subscribed (auto-played by LiveKit)');
        }
    });
    
    participant.on(LiveClient.ParticipantEvent.TrackUnsubscribed, (track) => {
        console.log(`Track unsubscribed from ${participant.identity}:`, track.kind);
    });
}

// Create video element for remote participant
function createRemoteVideoElement(participantId) {
    let videoElement = document.getElementById(`remote-video-${participantId}`);
    
    if (!videoElement) {
        videoElement = document.createElement('video');
        videoElement.id = `remote-video-${participantId}`;
        videoElement.autoplay = true;
        videoElement.playsinline = true;
        videoElement.style.width = '100%';
        videoElement.style.height = '100%';
        videoElement.style.objectFit = 'cover';
        
        // Add to DOM (you may need to adjust this based on your HTML structure)
        const container = document.querySelector(`.live-card [data-participant-id="${participantId}"]`);
        if (container) {
            container.innerHTML = '';
            container.appendChild(videoElement);
        }
        
        remoteVideoElements[participantId] = videoElement;
    }
    
    return videoElement;
}

// Remove video element for remote participant
function removeRemoteVideoElement(participantId) {
    const videoElement = remoteVideoElements[participantId];
    if (videoElement) {
        if (videoElement.srcObject) {
            videoElement.srcObject.getTracks().forEach(track => track.stop());
        }
        videoElement.remove();
        delete remoteVideoElements[participantId];
    }
}

// Cleanup all video elements
function cleanupVideoElements() {
    Object.keys(remoteVideoElements).forEach(id => {
        removeRemoteVideoElement(id);
    });
    if (localVideoElement && localVideoElement.srcObject) {
        localVideoElement.srcObject.getTracks().forEach(track => track.stop());
    }
    isVideoEnabled = false;
}

// Disconnect from LiveKit
async function disconnectLiveKit() {
    if (liveKitRoom) {
        await liveKitRoom.disconnect();
        liveKitRoom = null;
    }
    cleanupVideoElements();
}
```

### Step 6: Integrate with Existing `joinCall()` Function

Update your existing `joinCall()` to request WebRTC token:

```javascript
async function joinCall(callId) {
    // ... existing call join code ...
    
    // NEW: Request WebRTC token
    if (webrtcConfig && webrtcConfig.provider === 'livekit') {
        const isHost = ROOM_HOSTS && ROOM_HOSTS[callId] === userIdGlobal;
        const tokenData = await requestWebRTCToken(callId, isHost);
        
        if (tokenData) {
            const connected = await connectToLiveKit(tokenData);
            if (connected) {
                console.log('Video streaming initialized');
            }
        }
    }
    
    // ... rest of existing code ...
}
```

### Step 7: Handle Video Cleanup on Leave

Update your `leaveCall()` function:

```javascript
async function leaveCall(callId) {
    // NEW: Disconnect from WebRTC
    await disconnectLiveKit();
    
    // ... existing leave logic ...
}
```

### Step 8: Toggle Camera/Microphone (Optional)

Add these utility functions:

```javascript
async function toggleCamera(enabled) {
    if (!liveKitRoom) return;
    
    try {
        if (enabled) {
            await liveKitRoom.localParticipant.setCameraEnabled(true);
            showToast('Camera enabled');
        } else {
            await liveKitRoom.localParticipant.setCameraEnabled(false);
            showToast('Camera disabled');
        }
    } catch (error) {
        console.error('Camera toggle failed:', error);
        showToast('Camera toggle failed');
    }
}

async function toggleMicrophone(enabled) {
    if (!liveKitRoom) return;
    
    try {
        if (enabled) {
            await liveKitRoom.localParticipant.setMicrophoneEnabled(true);
            showToast('Microphone enabled');
        } else {
            await liveKitRoom.localParticipant.setMicrophoneEnabled(false);
            showToast('Microphone disabled');
        }
    } catch (error) {
        console.error('Microphone toggle failed:', error);
        showToast('Microphone toggle failed');
    }
}

async function shareScreen() {
    if (!liveKitRoom || !webrtcConfig.features.screen_share) return;
    
    try {
        await liveKitRoom.localParticipant.setScreenShareEnabled(true);
        showToast('Screen sharing started');
    } catch (error) {
        console.error('Screen share failed:', error);
        showToast('Screen share failed');
    }
}
```

---

## Part 3: Update HTML for Video Elements

Update your `createCallCard()` function to ensure video elements exist:

```javascript
function createCallCard(call) {
    const card = document.createElement('div');
    card.className = 'live-card rounded-xl p-3 md:p-4 cursor-pointer';
    card.innerHTML = `
        <div class="flex gap-3 md:gap-4 sm:flex-row flex-col">
            <div class="flex-shrink-0 w-full sm:w-28 h-44 sm:h-40 rounded-3xl bg-black relative overflow-hidden">
                <!-- Video element for this call -->
                <video id="remote-video-${call.id}" 
                       autoplay 
                       playsinline 
                       muted 
                       class="w-full h-full object-cover"></video>
                
                <!-- Live badge and viewers count -->
                <div class="live-pill absolute top-3 left-3 z-10">LIVE</div>
                <div class="text-xs text-white/90 absolute bottom-3 right-3 backdrop-blur-sm bg-black/40 rounded-full px-2 py-1 z-10">
                    ${call.participants} viewers
                </div>
            </div>
            
            <!-- Rest of card content -->
            <div class="flex-1 min-w-0 flex flex-col justify-between">
                <!-- ... existing content ... -->
            </div>
        </div>
    `;
    
    // ... rest of function ...
}
```

---

## Part 4: Error Handling and Fallbacks

```javascript
// Global error handler for WebRTC
window.addEventListener('error', (event) => {
    if (event.message && event.message.includes('WebRTC')) {
        console.error('WebRTC Error:', event.message);
        showToast('Video connection error: ' + event.message);
    }
});

// Handle connection failures
async function handleWebRTCFailure(error) {
    console.error('WebRTC operation failed:', error);
    
    if (error.message.includes('permission')) {
        showToast('Camera/microphone permission denied');
    } else if (error.message.includes('timeout')) {
        showToast('Video connection timeout');
    } else if (error.message.includes('network')) {
        showToast('Network error - check your connection');
    } else {
        showToast(`Video error: ${error.message}`);
    }
    
    // Fallback: continue with audio-only
    isVideoEnabled = false;
}
```

---

## Part 5: WebSocket Handler for WebRTC Tokens

Add this to your WebSocket `onmessage` handler:

```javascript
socket.onmessage = (event) => {
    try {
        const payload = JSON.parse(event.data);
        
        // ... existing handlers ...
        
        // NEW: Handle WebRTC token response
        if (payload.type === 'webrtc_token') {
            console.log('WebRTC token received');
            connectToLiveKit(payload).catch(handleWebRTCFailure);
        }
        
        // ... rest of handlers ...
    } catch (error) {
        console.error('WebSocket message error:', error);
    }
};
```

---

## Part 6: Testing

### Test 1: Basic Connection
1. Open learnflow.html
2. Join a live call
3. Check browser console for "Connected to LiveKit room"
4. Verify video element appears and is non-empty

### Test 2: Multi-User
1. Open same call in two browser windows
2. Both should see each other's video
3. Audio broadcasts from backend should play

### Test 3: Host vs Guest Permissions
1. Host should be able to publish video/audio
2. Guest video should appear in all browsers
3. Only host's Gemini responses should be broadcast

### Test 4: Error Scenarios
1. Disable camera/microphone → should get permission error
2. Disconnect network → should attempt reconnection
3. Leave call → should cleanup resources

---

## Configuration Options

### LiveKit-Specific (in `connectToLiveKit()`):

```javascript
const room = new LiveClient.Room({
    // Video constraints
    video: { 
        width: 1280,
        height: 720,
        frameRate: 30
    },
    // Audio handling
    audio: true,
    // Auto-subscribe to tracks
    autoSubscribe: true,
    // Dynacast for simulcast (multiple qualities)
    dynacast: true,
    // Screen share
    screenShare: {
        resolution: {
            width: 1920,
            height: 1080,
            frameRate: 15
        }
    }
});
```

### Connection Options:

```javascript
await liveKitRoom.connect(tokenData.url, tokenData.token, {
    autoSubscribe: true,
    maxRetries: 5,
    reconnectFallbackMs: 5000,
    peerConnectionTimeout: 15000,
    disconnectOnPageUnload: true,
});
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "CORS error" | Check CSRF token, ensure backend allows requests |
| "Connection refused" | Verify WebRTC provider URL is correct |
| "No camera/mic permission" | User must grant browser permissions |
| "Video not showing" | Check `createRemoteVideoElement()` is creating elements correctly |
| "Audio plays but video doesn't" | Video initialization is separate from audio (this is correct) |
| "Multiple audio streams" | WebSocket audio + WebRTC audio = double audio. Disable WebRTC audio if only listening |

---

## Browser Support

- ✅ Chrome/Chromium (v60+)
- ✅ Firefox (v55+)
- ✅ Safari (v12.1+)
- ✅ Edge (v79+)
- ❌ Internet Explorer (not supported)

---

## Next Steps

1. **Test with LiveKit instance**: Deploy LiveKit server or use managed service
2. **Add screen sharing**: Extend with `shareScreen()` function
3. **Add recording**: Use LiveKit recording API
4. **Add chat**: Combine text questions with WebRTC
5. **Optimize bandwidth**: Enable dynacast and simulcast for better quality

For detailed LiveKit documentation, see: https://docs.livekit.io/js/
