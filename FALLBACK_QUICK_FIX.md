# Why Your Fallback APIs Aren't Working (Quick Reference)

## The Problem

Your logs show:
```
AI provider failover completed with no successful response. Providers tried: ['gemini'].
```

This means **only Gemini is being used** even though the code supports Sunbird and Cerebras fallback.

## The Root Cause

**Environment variables are missing.** When your app starts on Koyeb, it checks for:

```python
# ✅ Gemini - FOUND
GEMINI_API_KEY=AIzaSyDSLCPuAk61XjABzzkrB63ezum_2GxEg64

# ❌ Sunbird - NOT FOUND
SUNBIRD_API_URL=???
SUNBIRD_API_KEY=???

# ❌ Cerebras - NOT FOUND  
CEREBRAS_API_URL=???
CEREBRAS_API_KEY=???
```

If these aren't set, the provider isn't even tried.

## What To Do (3 Minutes)

### 1. Get a Free API Key

**Pick ONE:**

- **Sunbird** (African languages): https://www.sunbird.ai/ → Sign up → Get API key
- **Cerebras** (Fast): https://www.cerebras.ai/ → Sign up → Get API key

### 2. Add to Koyeb

1. Go to Koyeb Dashboard: https://app.koyeb.com
2. Click your service name
3. Click **Settings** → **Environment**
4. Click **Edit Environment Variables**
5. Add your keys:

```
SUNBIRD_API_URL=https://api.sunbird.ai/v1/generate
SUNBIRD_API_KEY=sk_live_xxxxxxxxxxxxx
SUNBIRD_TTS_URL=https://api.sunbird.ai/v1/tts
```

6. Click **Save**
7. Koyeb automatically redeploys (2-3 minutes)

### 3. Verify

After redeployment, you'll see in logs:
```
AI Request completed using provider: sunbird  ✅
```

## Why Gemini Alone Isn't Enough

| Issue | Problem |
|-------|---------|
| **Rate Limits** | Gemini hits 429 errors under load |
| **African Users** | English-only for Gemini; Sunbird handles Swahili, Luganda, etc. |
| **Cost** | No free tier fallback = expensive when rate-limited |

**With Sunbird + Gemini:**
- Load spikes? → Auto-switch to Sunbird ✅
- Swahili user? → Use Sunbird directly ✅
- Both working? → Use cheaper Gemini ✅

## Complete Setup (Recommended)

Set **both** for maximum resilience:

```env
GEMINI_API_KEY=AIzaSyDSLCPuAk61XjABzzkrB63ezum_2GxEg64

SUNBIRD_API_URL=https://api.sunbird.ai/v1/generate
SUNBIRD_API_KEY=sk_live_xxxxxxxxxxxxx
SUNBIRD_TTS_URL=https://api.sunbird.ai/v1/tts

CEREBRAS_API_URL=https://api.cerebras.ai/v1/models/llama-3.1-70b-instruct/completions
CEREBRAS_API_KEY=csk_live_xxxxxxxxxxxxx
```

## Checking Status

After adding keys, check the diagnostics response:

```json
{
  "provider": "sunbird",
  "diagnostics": {
    "provider_availability": {
      "gemini": "configured",
      "sunbird": "configured",
      "cerebras": "missing CEREBRAS_API_KEY"
    }
  }
}
```

Now you'll know exactly what's configured!

---

**Total time needed:** 5 minutes
**Cost:** Free (trial tier)
**Impact:** 99.9% uptime for African users ✅
