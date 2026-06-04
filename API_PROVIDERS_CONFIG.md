# AI Provider Configuration Guide

This application supports multiple AI providers with automatic fallback. When Gemini hits rate limits or fails, the system will automatically switch to Sunbird or Cerebras.

## Provider Priority Order

The system tries providers in this order:

1. **Gemini** (Primary) - Fast and general-purpose
2. **Sunbird** (Fallback) - African languages, offline support, voice-first
3. **Cerebras** (Fallback) - Fast inference for large models

## Configuration

### 1. Gemini API (Primary - Already Configured)

```env
GEMINI_API_KEY=your-gemini-api-key-here
```

**Status:** ✅ Already set up
**Docs:** https://ai.google.dev/

---

### 2. Sunbird API (Recommended Fallback)

Sunbird specializes in **African languages and offline support**. Perfect for Nakintu AI's multilingual needs.

```env
SUNBIRD_API_URL=https://api.sunbird.ai/v1/generate
SUNBIRD_API_KEY=your-sunbird-api-key
SUNBIRD_TTS_URL=https://api.sunbird.ai/v1/tts
```

**Supported Languages:**
- African: Swahili, Luganda, Hausa, Yoruba, Igbo, Zulu, Shona, Xhosa, Amharic, etc.
- Major: English, French, Spanish, Portuguese, Arabic, Chinese, Japanese, Hindi

**Setup Steps:**
1. Go to https://sunbird.ai (or check their documentation)
2. Create an account and get your API keys
3. Add the credentials to your deployment platform (Koyeb, Heroku, etc.)

**Cost:** Check Sunbird's pricing page

---

### 3. Cerebras API (Alternative Fallback)

Cerebras offers ultra-fast inference, great for when Gemini is overloaded.

```env
CEREBRAS_API_URL=https://api.cerebras.ai/v1/models/llama-3.1-70b-instruct
CEREBRAS_API_KEY=your-cerebras-api-key
```

**Setup Steps:**
1. Go to https://www.cerebras.ai/
2. Sign up for API access
3. Get your API key from the dashboard
4. Add credentials to your deployment

**Cost:** Check Cerebras pricing

---

## How to Add Credentials (Koyeb Example)

If your app is deployed on Koyeb:

1. Go to your Koyeb dashboard
2. Select your service
3. Click **Settings** → **Environment**
4. Add each variable:
   ```
   SUNBIRD_API_URL=...
   SUNBIRD_API_KEY=...
   CEREBRAS_API_URL=...
   CEREBRAS_API_KEY=...
   ```
5. Redeploy your application

## Testing Fallback

The system automatically logs which provider is being used:

```
AI Request completed using provider: gemini
AI Request completed using provider: sunbird    # Fallback activated
AI Request completed using provider: cerebras   # Both gemini and sunbird failed
```

Check your application logs to verify the fallback is working.

## Monitoring

The `gemini_proxy` endpoint now returns provider information:

```json
{
  "text": "Your AI response here...",
  "provider": "sunbird",
  "language_code": "sw",
  "diagnostics": {
    "providers_tried": ["gemini", "sunbird"],
    "provider_errors": ["gemini: 429 Client Error: Too Many Requests"]
  }
}
```

## Rate Limit Behavior

- **Gemini hits limit (429):** System waits 1 second, retries once, then falls back to Sunbird/Cerebras
- **Sunbird/Cerebras unavailable:** System uses local fallback response
- **All providers fail:** Returns helpful error message prompting user to retry

## Recommendations

✅ **For Production:**
1. Keep Gemini (primary - most cost-effective for English)
2. Add **Sunbird** for African language support
3. Add **Cerebras** as secondary fallback

✅ **For African Users:**
1. Prioritize Sunbird (African languages, offline support)
2. Use Gemini as secondary fallback
3. Add Cerebras for redundancy

✅ **Cost Optimization:**
- Monitor usage to understand your typical load
- Start with just Gemini + Sunbird
- Add Cerebras only if needed

## Troubleshooting

**Q: Why is it still only using Gemini?**
A: Sunbird/Cerebras keys aren't set. Add them to environment variables and redeploy.

**Q: How do I know which provider is being used?**
A: Check application logs or inspect the API response's `provider` field.

**Q: Can I test fallback locally?**
A: Yes - temporarily disable Gemini API key to force fallback.

**Q: What if all providers fail?**
A: Users see a friendly message to retry in 2 seconds. Check your API keys and rate limits.
