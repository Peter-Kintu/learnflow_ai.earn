
    // Constants and Global Variables
    const chatLog = document.getElementById('chatLog');
    const stopSpeakingButton = document.getElementById('stopSpeakingButton');
    const recordButton = document.getElementById('recordButton');
    const voiceStatus = document.getElementById('voiceStatus');
    const chatInput = document.getElementById('chatInput');
    const languageSelector = document.getElementById('languageSelector');
    const sidebarMenu = document.getElementById('sidebarMenu');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    // NEW: Get the send button for potential status updates (though not strictly required)
    const sendChatButton = document.getElementById('sendChatButton');

    function toggleSidebar() {
        if (!sidebarMenu) return;
        sidebarMenu.classList.toggle('open');
        if (!sidebarOverlay) return;
        sidebarOverlay.style.display = sidebarMenu.classList.contains('open') ? 'block' : 'none';
    }

    function preFillQuestion(prompt) {
        const chatInput = document.getElementById('chatInput');
        if (!chatInput) return;
        chatInput.value = prompt;
        chatInput.focus();
    }


    const responseLimit = 10;
    const username = "user";
    const chatHistoryKey = `chatHistory-${username}`;
    const responseCountKey = `responseCount-${username}`;
    let responseCount = localStorage.getItem(responseCountKey) ? parseInt(localStorage.getItem(responseCountKey)) : 0;
    
    // 🔥 NEW GLOBAL VARIABLE: To store and pass the user's accurate context to the AI 🔥
    let userCurrentContext = {};
    let pendingPositiveFeedback = null;
    
    // --- Speech Synthesis Variables (TTS) ---
    let voices = [];
    let isSpeaking = false;
    
    // --- Speech Recognition Variables (STT) ---
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let isRecording = false;
    
    // 🔥 NEW CONSTANT: Set the African Language Code for Speech Recognition (STT) 🔥
    // Swahili (Tanzania) is generally the most robust African language supported by Chrome/browser STT.
    // Try other codes like 'ha-NG' (Hausa) or 'zu-ZA' (Zulu) if you prefer.
    const africanLanguageCode = 'sw-TZ'; 

    // --- API Configuration ---
    // NOTE: Replace the placeholder with your actual AI API key.
  
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      let cookie = cookies[i].trim();
      if (cookie.startsWith(name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

const proxyUrl = ""/dummy/url/"";
const chatHistoryUrl = ""/dummy/url/"";

// Example of how to trigger the message
async function handleUserSubmission() {
    const userMessage = chatInput.value.trim();
    if (!userMessage) return;

    const finalMessages = [
        { role: 'user', parts: [{ text: userMessage }] }
    ];

    const result = await sendMessage(finalMessages);

    if (result.isError) {
        appendMessage('ai', result.text, true);
        if (result.type === 'rate_limit') {
            startCooldown(2);
        }
    } else {
        appendMessage('ai', result.text);
    }
}

function startCooldown(seconds) {
    const btn = sendChatButton;
    const input = chatInput;
    if (!btn) return;

    btn.disabled = true;
    if (input) input.disabled = true;

    let remaining = seconds;
    const originalText = btn.innerText;
    const interval = setInterval(() => {
        btn.innerText = `Wait (${remaining}s)`;
        remaining--;

        if (remaining < 0) {
            clearInterval(interval);
            btn.disabled = false;
            if (input) input.disabled = false;
            btn.innerText = originalText;
        }
    }, 1000);
}

async function sendMessage(finalMessages) {
  try {
    const response = await fetch(proxyUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        contents: finalMessages,
        config: { temperature: 0.7, maxOutputTokens: 512 }
      })
    });

    // 1. Handle Rate Limiting (429)
    if (response.status === 429) {
      return { 
        isError: true, 
        type: 'rate_limit', 
        text: "The system is busy right now. Please try again after 2 seconds.",
      };
    }

    // 2. Handle other non-OK responses
    if (!response.ok) {
      await response.text().catch(() => '');
      return { 
        isError: true, 
        type: 'server_error', 
        text: "Sorry, I couldn’t reach the AI service. Please try again after 2 seconds.",
      };
    }

    // 3. Handle Successful Response
    const data = await response.json();
    return {
      text: data.text || "[No text returned]",
      provider: data.provider || 'unknown'
    };

  } catch (err) {
    // 4. Handle Network/Connection Errors
    console.error("Fetch error:", err);
    return { 
      isError: true, 
      type: 'network_error', 
      text: "Sorry, I couldn’t connect right now. Please try again after 2 seconds.",
    };
  }
}

    // 🔥 MODIFIED: systemInstruction - Updated for Modern Persona and Engagement 🔥
    const systemInstruction = `You are ** AI**, a modern, enthusiastic, and globally-aware educational guide developed by Kintu Peter. Your primary goal is to make learning engaging, personal, and fun for all users. Always maintain a warm, encouraging, and highly professional tone.

**INSTRUCTIONS FOR CONTEXT HANDLING:**
1. **ACCURATE USER CONTEXT:** The **CURRENT CONTEXT** section below will be dynamically updated by the user's browser (NOT by you). If a **Latitude/Longitude** is present, the user has explicitly shared their location, and you **MUST** use it for location-aware requests (like weather, directions, or local information).
2. **LOCATION LINK:** When location is successfully obtained, you **ARE PERMITTED** to provide a Google Maps URL for the user's current coordinates using the format: [View on Map](https://www.google.com/maps/search/?api=1&query=LAT,LNG).
3. **FALLBACK:** If no Latitude/Longitude is provided, use your **Virtual Location** (Kampala, Uganda) as a default.
4. **PRIVACY:** If the user asks *why* you know their location, state that it was explicitly provided by the browser after the user clicked 'Share Location.'
5. **TIME/DATE:** Always use the accurate time and date from the CURRENT CONTEXT when asked.

CURRENT CONTEXT:
- The browser will provide an up-to-date CURRENT CONTEXT via the userCurrentContext object (date, time, coordinates when available).
- Always prefer the dynamic userCurrentContext values over any static text. If coordinates are present use them for location-aware responses; otherwise use Kampala, Uganda as a reasonable virtual fallback.

**INSTRUCTIONS FOR REAL-TIME DATA & PREDICTIONS:**
- If the user asks for **real-time information (like news or current scores)**, use your internal browsing/search capability to provide the most current and accurate answer, acknowledging the inherent latency in news.
- If the user asks for **match predictions (e.g., football, soccer)**, use your vast knowledge base and current data to provide a detailed analysis and a most likely outcome, acting as an expert sports analyst.

**INSTRUCTIONS FOR CODE/HTML:**
- When providing code, use **markdown code blocks** (e.g., \`\`\`html) for clean, copy-pasteable output.
- When the user pastes or asks about HTML code, advise them that their input is safely displayed as **text** in the chat (not rendered) for security and clean editing.

Always respond in the language the user is using, maintaining context and educational quality.`;
    
    // --- Function to get and display accurate local date/time ---
    function updateAccurateLocalTime() {
        const now = new Date();
        
        // Format the date (e.g., Friday, December 6, 2025)
        const dateOptions = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
        const dateString = now.toLocaleDateString(undefined, dateOptions);

        // Format the time (e.g., 9:04 PM EAT)
        const timeOptions = { hour: '2-digit', minute: '2-digit', hour12: true, timeZoneName: 'short' };
        const timeString = now.toLocaleTimeString(undefined, timeOptions);
        
        // This is the accurate, user-local time and date for the AI context
        const localTimeText = `${dateString}, and the time is ${timeString}`; 
        
        // Update the global context variable
        userCurrentContext.currentTimeAndDate = localTimeText;
        
        // 🔥 UPDATE: Update the display element in the header
        const displayElement = document.getElementById('localTimeDisplay');
        if (displayElement) {
            displayElement.textContent = `Your local time: ${timeString} on ${dateString}`;
        }
        
        // Re-run every second to keep time accurate
        setTimeout(updateAccurateLocalTime, 1000); 
    }

    // --- Function to get the user's coordinates and pass them to the AI ---
    function getUserLocation() {
        // 1. Check if the browser supports the Geolocation API
        if ("geolocation" in navigator) {
            
            // Options for accuracy and timeout (as requested: high accuracy)
            const options = {
                enableHighAccuracy: true, // Request the best possible result (more accurate)
                timeout: 5000,            // Maximum time to wait for a result (5 seconds)
                maximumAge: 0             // Do not use a cached position
            };

            // 2. Request the user's current position (will trigger a permission prompt)
            // Note: We already appended the user's query in typeQuery()
            appendMessage('ai', 'Waiting for location permission...');
            
            navigator.geolocation.getCurrentPosition(
                // Success Callback: position is available
                (position) => {
                    const lat = position.coords.latitude;
                    const lng = position.coords.longitude;
                    const accuracy = position.coords.accuracy;
                    
                    // Update global context
                    userCurrentContext.latitude = lat;
                    userCurrentContext.longitude = lng;
                    
                    // STICKING TO THE INSTRUCTION'S FORMAT:
                    const mapLink = `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`;
                    const mapLinkMarkdown = `[View Your Location on Google Maps](${mapLink})`;
                    // 3. Inform the user in the chat (NOW INCLUDES LINK)
                    const aiMessage = `Location update successful! Your coordinates (Lat: ${lat.toFixed(4)}, Lng: ${lng.toFixed(4)}) have been saved with an accuracy of ${accuracy.toFixed(0)} meters. I will now use this for location-aware queries and directions.

${mapLinkMarkdown}

Please proceed with your location-based query (e.g., "What is the weather like here?").`;
                    
                    // Use the existing 'appendMessage' function to speak the message
                    appendMessage('ai', aiMessage); 
                },
                // Error Callback: handles when the user denies permission or an error occurs
                (error) => {
                    console.error("Error getting user location:", error.code, error.message);
                    
                    let errorMessage = "Unable to retrieve your location.";
                    if (error.code === error.PERMISSION_DENIED) {
                        errorMessage = "Location access was denied. Please allow location sharing in your browser settings and try again.";
                    } else if (error.code === error.TIMEOUT) {
                        errorMessage = "Timed out while trying to get location. Try again.";
                    } else {
                         errorMessage = `Location error (${error.code}): ${error.message}`;
                    }
                    
                    // Show error message to the user in the chat log (using existing function)
                    appendMessage('ai', errorMessage, true);
                },
                options // Pass the options object for high accuracy
            );
        } else {
            // Geolocation is not supported by the browser
            const notSupportedMsg = "Error: Your browser doesn't support geolocation.";
            appendMessage('ai', notSupportedMsg, true);
        }
    }


    /**
     * Cleans the AI response text by removing markdown formatting and disruptive symbols
     * before text-to-speech conversion.
     * @param {string} text The raw text from the API.
     * @returns {string} The cleaned text.
     */
    function cleanText(text) {
        let cleaned = text;

        // 1. Remove link/citation brackets and their content
        cleaned = cleaned.replace(/\[(.*?)\]/g, '$1'); // Keep content inside brackets, remove brackets themselves

        // 2. Remove common markdown bold/italic/strikethrough symbols (**, *, __, _, ~~)
        cleaned = cleaned.replace(/(\*\*|__)(.*?)\1/g, '$2'); // Removes ** and __ for bold/strong
        cleaned = cleaned.replace(/(\*|_)(.*?)\1/g, '$2'); // Removes * and _ for italics/emphasis
        cleaned = cleaned.replace(/~~(.*?)~~/g, '$1'); // Removes ~~ for strikethrough

        // 3. Remove list markers, headings, and specific disruptive punctuation
        cleaned = cleaned.replace(/^\s*[-*+]+\s+/gm, ''); // Removes list markers at the start of lines
        cleaned = cleaned.replace(/#+\s*/g, ''); // Removes heading symbols
        cleaned = cleaned.replace(/"/g, ''); // Remove all double quotes
        cleaned = cleaned.replace(/`/g, ''); // Remove backticks
        cleaned = cleaned.replace(/---/g, ' '); // Remove triple dashes (horizontal rule)
        cleaned = cleaned.replace(/--/g, ' '); // Remove double dashes
        cleaned = cleaned.replace(/([^a-zA-Z0-9])\s*-\s*([^a-zA-Z0-9])/g, ' '); // Remove standalone dashes
        cleaned = cleaned.replace(/[>≥≤<«»]/g, ' '); // Remove comparison/bracket symbols

        // 4. Clean up excessive whitespace that might result from removals
        cleaned = cleaned.replace(/\s\s+/g, ' '); // Replace multiple spaces with a single space
        
        // 5. Specifically remove code blocks entirely for speech synthesis
        cleaned = cleaned.replace(/```.*?```/gs, ' '); // Remove code blocks

        return cleaned.trim(); // Trim leading/trailing whitespace
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatAiResponseHtml(text) {
        if (!text) return '';

        try {
            // Normalize line endings and trim whitespace
            const normalizedText = text.replace(/\r\n/g, '\n').trim();

            // Use marked.js to parse markdown to HTML
            // Handles headings, bold/italic, lists, tables, code blocks, etc.
            let html = marked.parse(normalizedText, {
                breaks: true,
                gfm: true,
                headerIds: false,
                smartLists: true,
                smartypants: true,
                mangle: false
            });
            
            // Add inline styling for common markdown output elements
            html = html.replace(/<table>/g, '<table style="border-collapse: collapse; width: 100%; margin: 10px 0;">');
            html = html.replace(/<th>/g, '<th style="border: 1px solid #e2e8f0; padding: 8px; background: #eef2ff; font-weight: 700;">');
            html = html.replace(/<td>/g, '<td style="border: 1px solid #e2e8f0; padding: 8px;">');
            html = html.replace(/<code>/g, '<code style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-family: monospace;">');
            html = html.replace(/<pre>/g, '<pre style="background: #f1f5f9; padding: 12px; border-radius: 8px; overflow-x: auto; margin: 10px 0;">');
            html = html.replace(/<h1>/g, '<h1 style="font-size: 1.5em; margin: 15px 0 10px; font-weight: 800;">');
            html = html.replace(/<h2>/g, '<h2 style="font-size: 1.3em; margin: 12px 0 8px; font-weight: 700;">');
            html = html.replace(/<h3>/g, '<h3 style="font-size: 1.1em; margin: 10px 0 6px; font-weight: 700;">');
            html = html.replace(/<ul>/g, '<ul style="margin: 10px 0; padding-left: 20px;">');
            html = html.replace(/<ol>/g, '<ol style="margin: 10px 0; padding-left: 20px;">');
            html = html.replace(/<li>/g, '<li style="margin: 4px 0;">');

            return html;
        } catch (error) {
            console.error('Error parsing markdown:', error);
            return `<p>${escapeHtml(text)}</p>`;
        }
    }

    // ## NEW FUNCTION: Simple Language Guessing for TTS (Crucial Update!) ##
    /**
     * Attempts a basic guess of the language based on keywords to select the
     * correct TTS pronunciation engine.
     * @param {string} text The text to analyze.
     * @returns {string} The guessed BCP-47 language tag (e.g., 'sw-TZ', 'lg-UG', 'en-US').
     */
    function guessTextLanguage(text) {
        const lowerText = text.toLowerCase();
        
        // Swahili (sw) keywords: mambo, habari, asante, tafadhali, sijui, jambo
        if (lowerText.includes('mambo') || lowerText.includes('asante') || lowerText.includes('tafadhali') || lowerText.includes('swahili') || lowerText.includes('jambo') || lowerText.includes('habari')) {
            return 'sw-TZ'; // Swahili
        }

        // Luganda (lg) keywords: webale, otya, kye, kyokka, omulimu, oli otya
        if (lowerText.includes('webale') || lowerText.includes('otya') || lowerText.includes('luganda') || lowerText.includes('oli otya')) {
            return 'lg-UG'; // Luganda
        }

        // Hausa (ha) keywords: sannu, yaya, ina, me, Hausa, ina kwana
        if (lowerText.includes('sannu') || lowerText.includes('yaya') || lowerText.includes('hausa') || lowerText.includes('ina kwana')) {
            return 'ha-NG'; // Hausa
        }
        
        // Zulu/Xhosa (zu/xh) keywords: sawubona, yebo, ngiyabonga, zulu
        if (lowerText.includes('sawubona') || lowerText.includes('ngiyabonga') || lowerText.includes('zulu')) {
            return 'zu-ZA'; // Zulu
        }

        // Yoruba (yo) keywords: kaabo, e ku, kini, Yoruba
        if (lowerText.includes('kaabo') || lowerText.includes('e ku') || lowerText.includes('kini') || lowerText.includes('yoruba')) {
            return 'yo-NG'; // Yoruba
        }

        // Default to English if no clear non-English marker is found
        return 'en-US'; 
    }
    
    // ## TTS Functions (MODIFIED: speakText) ##
    function populateVoices() {
        voices = speechSynthesis.getVoices();
    }
    populateVoices();
    if (speechSynthesis.onvoiceschanged !== undefined) {
        speechSynthesis.onvoiceschanged = populateVoices;
    }

    function speakText(text) {
        if (!('speechSynthesis' in window)) {
            console.warn("Speech Synthesis not supported in this browser.");
            return;
        }

        stopSpeaking();
        isSpeaking = true;
        if (stopSpeakingButton) {
            stopSpeakingButton.style.display = 'block';
        }

        const utterance = new SpeechSynthesisUtterance(text);

        // 🔥 CRITICAL UPDATE: Guess the language of the text
        const targetLangCode = guessTextLanguage(text);

        // MODIFIED: Change the voice tone (pitch) and rate (speed)
        utterance.pitch = 1.2; // Higher tone (e.g., 1.2)
        utterance.rate = 0.95; // Slightly slower speed (e.g., 0.95)

        // Enhanced Voice Selection for Multilingual/African Languages (Now Male-Only Preference)
   const voicePreferences = [
    // 🔥 PRIORITY 1: EXPLICIT MALE VOICE (Daniel) - Removed Samantha
    { name: 'Daniel', keyword: 'Daniel' },     // The preferred male voice.
    
    // PRIORITY 2: Highest Quality & Neutral Voices (Best cross-device performance)
    { name: 'Google', keyword: 'Multi' },
    { name: 'Microsoft', keyword: 'Multi' },
    { name: 'Amazon', keyword: 'Multi' },
    
    // PRIORITY 3: African-related languages (Explicit Regional Match)
    { lang: 'en-ZA', name: 'South African' }, 
    { lang: 'zu', name: 'Zulu' }, 
    { lang: 'sw', name: 'Swahili' }, 
    { lang: 'ha', name: 'Hausa' }
];
// NOTE: The female voice ('Samantha') has been removed to ensure an exclusively male/neutral voice selection.
        let selectedVoice = null;
        
        // 1. Check for a voice that matches the GUESSED base language (e.g., find any voice with 'sw' language code for 'sw-TZ' text)
        const baseLang = targetLangCode.split('-')[0].toLowerCase();
        selectedVoice = voices.find(voice => voice.lang.split('-')[0].toLowerCase() === baseLang);
        
        // 2. Fallback to preferred voices if no exact language base match
        if (!selectedVoice) {
            for (let pref of voicePreferences) {
                // Find a voice by name OR by language code match
                selectedVoice = voices.find(voice => 
                    (voice.name.includes(pref.name || pref.keyword)) || 
                    (pref.lang && voice.lang.toLowerCase().includes(pref.lang.toLowerCase()))
                );
                if (selectedVoice) break;
            }
        }

        // Final fallback: any voice with an English language code
        if (!selectedVoice) {
            selectedVoice = voices.find(voice => voice.lang.includes('en'));
        }

        // If a voice is found, set it
        if (selectedVoice) {
            utterance.voice = selectedVoice;
        }
        
        // 🔥 CRITICAL FIX: Always set the utterance language to the GUESSED language code.
        // This is the most important step for correct pronunciation, even with an English voice.
        utterance.lang = targetLangCode; 


        utterance.onend = () => {
            isSpeaking = false;
            if (stopSpeakingButton) {
                stopSpeakingButton.style.display = 'none';
            }
        };

        utterance.onerror = (event) => {
            console.error('SpeechSynthesisUtterance.onerror', event);
            isSpeaking = false;
            if (stopSpeakingButton) {
                stopSpeakingButton.style.display = 'none';
            }
        };

        speechSynthesis.speak(utterance);
    }

    function stopSpeaking() {
        if (typeof speechSynthesis !== 'undefined' && isSpeaking) {
            speechSynthesis.cancel();
            isSpeaking = false;
            if (stopSpeakingButton) {
                stopSpeakingButton.style.display = 'none';
            }
        }
    }

    function initSpeechRecognition() {
        if (!SpeechRecognition) {
            console.warn('Speech recognition is not supported by this browser.');
            return;
        }

        recognition = new SpeechRecognition();
        recognition.lang = africanLanguageCode;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = () => {
            isRecording = true;
            if (recordButton) {
                recordButton.classList.add('recording');
                recordButton.title = 'Stop Recording';
            }
            if (voiceStatus) {
                voiceStatus.textContent = 'Listening...';
            }
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            if (chatInput) {
                chatInput.value = transcript;
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (voiceStatus) {
                voiceStatus.textContent = 'Speech recognition error. Try again.';
            }
            resetRecordingState();
        };

        recognition.onend = () => {
            resetRecordingState();
        };
    }

    function resetRecordingState() {
        isRecording = false;
        recordButton.classList.remove('recording');
        recordButton.title = 'Start Recording';
        chatInput.placeholder = 'Type your question or tap the mic to speak...';
    }

    function toggleRecording() {
        if (!recognition) {
            initSpeechRecognition();
            if (!recognition) return; // Exit if init failed
        }
        
        if (isRecording) {
            recognition.stop();
        } else {
            // Stop any ongoing speech before starting a recording
            stopSpeaking(); 
            recognition.start();
        }
    }

    // ## Chat UI Functions ##
    function appendMessage(sender, text, isError = false, positiveFeedback = false) {
        const normalizedSender = sender === 'model' ? 'ai' : sender;
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${normalizedSender} ${isError ? 'error' : ''}`;
        messageDiv.dataset.positiveFeedback = positiveFeedback ? 'true' : 'false';

        const avatarIcon = normalizedSender === 'ai' ? '🎓' : '👤';
        const profileLabel = normalizedSender === 'ai' ? 'Nakintu AI' : 'You';

        const actionButtons = normalizedSender === 'ai' ? `
            <div class="message-actions">
                <button type="button" class="ai-action-button copy-button">Copy</button>
                <button type="button" class="ai-action-button positive-button">Helpful</button>
            </div>` : '';

        messageDiv.innerHTML = `
            <div class="avatar">${avatarIcon}</div>
            <div class="content">
                <strong>${profileLabel}</strong>
                <div class="message-text"></div>
                ${actionButtons}
            </div>`;

        const contentDiv = messageDiv.querySelector('.message-text');
        chatLog.appendChild(messageDiv);

        function attachAiActions(rawText) {
            const copyButton = messageDiv.querySelector('.copy-button');
            const positiveButton = messageDiv.querySelector('.positive-button');
            let currentPositiveFeedback = messageDiv.dataset.positiveFeedback === 'true';

            if (copyButton) {
                copyButton.addEventListener('click', async () => {
                    try {
                        await navigator.clipboard.writeText(rawText);
                        copyButton.textContent = 'Copied!';
                        setTimeout(() => { copyButton.textContent = 'Copy'; }, 1600);
                    } catch (err) {
                        console.error('Copy failed:', err);
                        copyButton.textContent = 'Retry';
                        setTimeout(() => { copyButton.textContent = 'Copy'; }, 1600);
                    }
                });
            }

            if (positiveButton) {
                positiveButton.classList.toggle('liked', currentPositiveFeedback);
                positiveButton.textContent = 'Helpful';

                positiveButton.addEventListener('click', () => {
                    currentPositiveFeedback = !currentPositiveFeedback;
                    messageDiv.dataset.positiveFeedback = currentPositiveFeedback ? 'true' : 'false';
                    positiveButton.classList.toggle('liked', currentPositiveFeedback);
                    if (currentPositiveFeedback) {
                        pendingPositiveFeedback = 'The user indicated the previous AI answer was helpful. Continue in the same supportive educational style and maintain the helpful direction.';
                    } else {
                        pendingPositiveFeedback = null;
                    }
                    saveChatHistory();
                });
            }
        }

        if (normalizedSender === 'ai') {
            // For AI messages: render markdown as HTML immediately (no typewriter)
            contentDiv.innerHTML = formatAiResponseHtml(text);
            saveChatHistory();
            const speakableText = cleanText(text);
            speakText(speakableText);
            attachAiActions(text);
        } else {
            // For user messages: just show plain text
            contentDiv.textContent = text;
            saveChatHistory();
        }
        
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function addLoader() {
        const loaderDiv = document.createElement('div');
        loaderDiv.className = 'loader';
        loaderDiv.id = 'chatLoader';
        loaderDiv.textContent = 'Nakintu is composing a response...';
        chatLog.appendChild(loaderDiv);
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function removeLoader() {
        const loader = document.getElementById('chatLoader');
        if (loader) {
            loader.remove();
        }
    }

    // ## API Interaction ##

    async function generateAiResponse(prompt) {
  if (!prompt || sendChatButton.disabled) return;

  appendMessage('user', prompt);
  chatInput.value = '';
  sendChatButton.disabled = true;
  addLoader();

  const history = getChatHistory().map(item => ({
    role: item.role === 'ai' ? 'model' : item.role,
    parts: [{ text: item.text }]
  }));

  const languageCode = (languageSelector && languageSelector.value) || 'auto';
  let currentSystemInstruction = systemInstruction;

  if (userCurrentContext.currentTimeAndDate) {
    const [datePart, timePart] = userCurrentContext.currentTimeAndDate.split(', and the time is ');
    currentSystemInstruction = currentSystemInstruction.replace(/The user's accurate local date is \*\*(.*?)\*\*/, `The user's accurate local date is **${datePart}**`);
    currentSystemInstruction = currentSystemInstruction.replace(/The user's accurate local time is \*\*(.*?)\*\*/, `The user's accurate local time is **${timePart}**`);
  }

  if (userCurrentContext.latitude && userCurrentContext.longitude) {
    currentSystemInstruction += `\n- The user's specific coordinates are: **Lat ${userCurrentContext.latitude}, Lng ${userCurrentContext.longitude}**. Use this for location-aware requests and directions.`;
  }

    if (pendingPositiveFeedback) {
        currentSystemInstruction += `\n- USER FEEDBACK: ${pendingPositiveFeedback}`;
        pendingPositiveFeedback = null;
    }

  const lastMessage = history.length ? history[history.length - 1] : null;
  const maxHistoryItems = 10;
  const trimmedHistory = history.slice(-maxHistoryItems);
  const fullContents = [...trimmedHistory];

  if (!lastMessage || lastMessage.role !== 'user' || lastMessage.parts[0].text !== prompt) {
    fullContents.push({ role: 'user', parts: [{ text: prompt }] });
  }

  try {
    const response = await fetch(proxyUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken')
      },
      body: JSON.stringify({
        contents: fullContents,
        systemInstruction: currentSystemInstruction,
        language_code: languageCode,
        voice: false,
        config: {
          temperature: 0.7,
          maxOutputTokens: 2048
        }
      })
    });
    const data = await response.json();
    const aiText = data.text || "I’m sorry, I couldn’t generate a response right now. Please try again after 2 seconds.";

    responseCount++;
    localStorage.setItem(responseCountKey, responseCount);

    removeLoader();
    appendMessage('ai', aiText);
  } catch (error) {
    console.error('AI proxy error:', error);
    removeLoader();
    const errorMessage = "Sorry, I couldn’t connect right now. Please try again after 2 seconds.";
    appendMessage('ai', errorMessage, true);
    speakText(cleanText(errorMessage));
  } finally {
    sendChatButton.disabled = false;
  }
}
    // --- User Actions ---
    function typeQuery() {
        const query = chatInput.value.trim();
        
        if (!query) return;

        // 🔥 NEW LOGIC: Check for location-sharing keyword and trigger getUserLocation 🔥
        const lowerQuery = query.toLowerCase();
        if (lowerQuery.includes('share my location') || lowerQuery.includes('get my location') || lowerQuery.includes('update location')) {
            // Since this is a user action, append the user's message first
            appendMessage('user', query);
            
            // Clear the input and trigger the location request instead of the AI
            chatInput.value = ''; 
            getUserLocation();
            return; 
        }
        
        if (query) {
            generateAiResponse(query);
        }
    }

    function handleKeydown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault(); // Prevents a new line in the textarea
            typeQuery();
        }
        // Optional: Auto-resize textarea
        chatInput.style.height = 'auto';
        chatInput.style.height = (chatInput.scrollHeight) + 'px';
    }

    function summarizeChat() {
    stopSpeaking(); // Stop current speech
    
    const history = getChatHistory();
    if (history.length === 0) {
        appendMessage('ai', "There is no conversation history to summarize.", true);
        return;
    }

    const summaryPrompt = "Please generate a concise, bullet-point summary of the key topics, concepts, and conclusions from the following conversation history. Respond in a professional, educational tone.";
    
    // Add a temporary loader message
    const loaderMsgDiv = document.createElement('div');
    loaderMsgDiv.className = 'chat-message ai';
    loaderMsgDiv.id = 'summaryLoader';
    loaderMsgDiv.innerHTML = '<strong>Ai (Summary):</strong> <div class="loader-small"></div> Generating summary...';
    chatLog.appendChild(loaderMsgDiv);
    chatLog.scrollTop = chatLog.scrollHeight;
    
    // Prepare the conversation payload for the summary request
    const conversationContent = history.map(item => `${item.role.toUpperCase()}: ${item.text}`).join('\n');
    const summaryRequestContent = summaryPrompt + "\n\n--- Conversation History ---\n" + conversationContent;
    
    const summaryContents = [
        { role: "user", parts: [{ text: summaryRequestContent }] }
    ];

    // Send a dedicated API call for the summary
    fetch(proxyUrl, { 
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken') 
        },
        body: JSON.stringify({
            contents: summaryContents,
            config: { 
                temperature: 0.2,
                maxOutputTokens: 1024
            }
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.text().then(text => {
                try {
                    const err = JSON.parse(text);
                    throw new Error((err && err.error && err.error.message) || `Status ${response.status}: Unknown API Error`);
                } catch (e) {
                    throw new Error(`Non-JSON response (Status ${response.status}). Check server/proxy connection.`);
                }
            });
        }
        return response.json();
    })
    .then(data => {
        const displayText = data.text || "Could not generate summary.";
        
        const loader = document.getElementById('summaryLoader');
        if (loader) { loader.remove(); }
        
        const aiMsgDiv = document.createElement('div');
        aiMsgDiv.className = "chat-message ai";
        
        const contentSpan = document.createElement('span');
        aiMsgDiv.appendChild(contentSpan);
        chatLog.appendChild(aiMsgDiv);
        
        let i = 0;
        function typeSummary() {
            if (i < displayText.length) {
                contentSpan.textContent += displayText.charAt(i);
                i++;
                setTimeout(typeSummary, 10);
            } else {
                saveChatHistory();
                const speakableText = cleanText(displayText);
                speakText(speakableText);
            }
            chatLog.scrollTop = chatLog.scrollHeight;
        }
        typeSummary();
    })
    .catch(error => {
        const loader = document.getElementById('summaryLoader');
        if (loader) { loader.remove(); }
        const errorMsgDiv = document.createElement('div');
        errorMsgDiv.className = "chat-message error";
        const summaryErrorText = "Could not generate summary due to a connection error: " + error.message;
        errorMsgDiv.innerHTML = `<strong>Ai (Summary):</strong> <span class="text-xl inline-block mr-2">🚨</span> ${cleanText(summaryErrorText)}`;
        chatLog.appendChild(errorMsgDiv);
        saveChatHistory();
        speakText("I encountered an error while generating the summary.");
    });
}
            
    function exportChat() {
        const history = getChatHistory();
        if (history.length === 0) {
            alert("No chat history to export!");
            return;
        }

        let exportText = ` Nakintu AI Chat Export for ${username}\nDate: ${new Date().toLocaleString()}\n\n`;
        history.forEach(item => {
            exportText += `${item.role.toUpperCase()}: ${item.text}\n\n`;
        });

        const blob = new Blob([exportText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `learnflow_chat_${username}_${Date.now()}.txt`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    function clearChat() {
        if (confirm("Are you sure you want to clear the entire chat history? This action cannot be undone.")) {
            localStorage.removeItem(chatHistoryKey);
            
            chatLog.innerHTML = `
                <div class="chat-message ai">
                    <strong>Nakintu AI:</strong>
                    <span class="text-gray-400">
                        Hello! I'm Nakintu AI, your modern learning partner. Ask me anything—from local history to global trends—and let's make learning fun!
                    </span>
                </div>
            `;
            stopSpeaking();
            speakText("Chat history cleared. How can I help you start your learning journey today?");
            chatLog.scrollTop = chatLog.scrollHeight;
        }
    }

    // ## Local Storage Management ##

    function saveChatHistory() {
        const finalMessages = [];
        chatLog.querySelectorAll('.chat-message').forEach(msgDiv => {
            const role = msgDiv.classList.contains('user') ? 'user' : 'ai';
            const textElement = msgDiv.querySelector('.message-text');
            const text = textElement ? textElement.textContent.trim() : msgDiv.textContent.trim();
            const positiveFeedback = msgDiv.dataset.positiveFeedback === 'true';

            if (text) {
                finalMessages.push({ role, text, positiveFeedback });
            }
        });

        localStorage.setItem(chatHistoryKey, JSON.stringify(finalMessages));
    }

    function getChatHistory() {
        const storedHistory = localStorage.getItem(chatHistoryKey);
        return storedHistory ? JSON.parse(storedHistory) : [];
    }

    function loadChatHistory() {
        // ✅ NEW: Fetch chat history from server database
        // This ensures messages persist even after browser closes
        
        fetch(chatHistoryUrl)
            .then(response => response.json())
            .then(data => {
                if (!chatLog) return;
                chatLog.innerHTML = ''; // Clear initial state
                
                        const messages = data.messages || [];
                
                if (messages.length === 0) {
                    // Show welcome message if no history
                    chatLog.innerHTML = `
                        <div class="chat-message ai">
                            <div class="avatar">🎓</div>
                            <div class="content">
                                <strong>Nakintu AI:</strong>
                                <p>Hello! I'm Nakintu AI, your modern learning partner. Ask me anything—from local history to global trends—and let's make learning fun!</p>
                            </div>
                        </div>
                    `;
                    return;
                }
                
                // Render all messages from database
                messages.forEach(msg => {
                    appendMessage(msg.role === 'model' ? 'ai' : msg.role, msg.text, false, false);
                });
                
                chatLog.scrollTop = chatLog.scrollHeight;
            })
            .catch(error => {
                console.error('Failed to load chat history:', error);
                // Fallback to localStorage if server unavailable
                loadChatHistoryFromLocalStorage();
            });
    }

    function loadChatHistoryFromLocalStorage() {
        // Fallback function for offline scenarios
        const history = getChatHistory();
        if (!chatLog) return;
        chatLog.innerHTML = '';
        
        if (history.length === 0) {
            chatLog.innerHTML = `
                <div class="chat-message ai">
                    <div class="avatar">🎓</div>
                    <div class="content">
                        <strong>Nakintu AI:</strong>
                        <p>Hello! I'm Nakintu AI, your modern learning partner. Ask me anything—from local history to global trends—and let's make learning fun!</p>
                    </div>
                </div>
            `;
            return;
        }

        history.forEach(item => {
            const normalizedRole = item.role === 'model' ? 'ai' : item.role;
            appendMessage(normalizedRole, item.text, false, item.positiveFeedback || false);
        });
    }

    // Initialize
    window.onload = () => {
        loadChatHistory();
        initSpeechRecognition(); // Initialize recognition on page load

        if (sendChatButton) {
            sendChatButton.addEventListener('click', typeQuery);
        }
        if (chatInput) {
            chatInput.addEventListener('keydown', handleKeydown);
        }
        
        // --- ADDED: Start the local time display ---
        updateAccurateLocalTime(); 
    };
