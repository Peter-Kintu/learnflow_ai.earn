# Koyeb AI Provider Configuration Guide

Your application is correctly set up for multi-provider fallback, but **Sunbird and Cerebras API keys are not configured on Koyeb**. Here's how to add them.

## Current Status

✅ **Gemini** - Configured and hitting rate limits (429)
❌ **Sunbird** - Not configured
❌ **Cerebras** - Not configured

The logs show:
```
AI provider failover completed with no successful response. Providers tried: ['gemini']. 
```

This means only Gemini is available. We need to add Sunbird and/or Cerebras.

---

## Step 1: Get Free/Trial API Keys

### Option A: Sunbird (Recommended for African Languages)

Sunbird specializes in African languages and has excellent support for Swahili, Luganda, etc.

**Free Tier:**
- Visit: https://www.sunbird.ai/
- Click "Get Started" or "Sign Up"
- You'll get free credits to test the API
- Navigate to Dashboard → API Keys → Create New Key

**Environment Variables to Add:**
```
SUNBIRD_API_URL=https://api.sunbird.ai/v1/generate
SUNBIRD_API_KEY=sk_live_xxxxxxxxxxxxx
SUNBIRD_TTS_URL=https://api.sunbird.ai/v1/tts
```

---

### Option B: Cerebras (Ultra-Fast Inference)

Cerebras provides very fast inference - great for handling load spikes.

**Free Tier:**
- Visit: https://www.cerebras.ai/
- Click "Get Started" or "Create Account"
- Go to Dashboard → API Settings
- Generate API Key

**Environment Variables to Add:**
```
CEREBRAS_API_URL=https://api.cerebras.ai/v1/models/llama-3.1-70b-instruct/completions
CEREBRAS_API_KEY=csk_live_xxxxxxxxxxxxx
```

---

## Step 2: Add Environment Variables to Koyeb

### Via Koyeb Dashboard (Easiest):

1. **Go to Koyeb Dashboard**
   - Open https://app.koyeb.com

2. **Select Your Service**
   - Click on your Nakintu AI service

3. **Settings → Environment**
   - Click the "Settings" tab
   - Click "Environment" section
   - Click "Edit Environment Variables"

4. **Add Variables**
   - Paste your Sunbird/Cerebras keys exactly as shown above
   - Click "Save"

5. **Redeploy**
   - Koyeb will automatically redeploy your service
   - Wait 2-3 minutes for the new instance to start

### Via Command Line (If you use Koyeb CLI):

```bash
koyeb service update nakintu-ai \
  --env SUNBIRD_API_URL=https://api.sunbird.ai/v1/generate \
  --env SUNBIRD_API_KEY=sk_live_xxxxxxxxxxxxx \
  --env SUNBIRD_TTS_URL=https://api.sunbird.ai/v1/tts
```

Then redeploy:
```bash
koyeb service redeploy nakintu-ai
```

---

## Step 3: Verify Fallback is Working

After deployment, make a request to your app and check the logs:

**Desired logs:**
```
AI Request completed using provider: sunbird
Diagnostics: {'providers_tried': ['sunbird'], ...}
```

Or if using Cerebras:
```
AI Request completed using provider: cerebras
Diagnostics: {'providers_tried': ['cerebras', 'sunbird'], ...}
```

**Still seeing Gemini-only logs?**
```
AI Request completed using provider: fallback
```

This means the environment variables haven't been picked up. Check:
1. Did you click "Save" in Koyeb?
2. Did the service redeploy (check Koyeb Dashboard)?
3. Wait 5 minutes and try again (caching)

---

## Recommended Configuration

For **best results with your African users**, use **both Sunbird + Gemini**:

```env
# Primary (Gemini - already set)
GEMINI_API_KEY=AIzaSyDSLCPuAk61XjABzzkrB63ezum_2GxEg64

# Fallback 1 (Sunbird - for African languages)
SUNBIRD_API_URL=https://api.sunbird.ai/v1/generate
SUNBIRD_API_KEY=sk_live_xxxxxxxxxxxxx
SUNBIRD_TTS_URL=https://api.sunbird.ai/v1/tts

# Optional Fallback 2 (Cerebras - for speed)
CEREBRAS_API_URL=https://api.cerebras.ai/v1/models/llama-3.1-70b-instruct/completions
CEREBRAS_API_KEY=csk_live_xxxxxxxxxxxxx
```

### Provider Priority (With This Config):

```
Request (Swahili) → Sunbird ✅ (Best for African languages)
Request (English)  → Gemini ✅ (Fastest & cheapest)
If Gemini rate-limits → Sunbird ✅ (Fallback)
If Sunbird unavailable → Cerebras ✅ (Secondary fallback)
If all fail → Local response (Graceful degradation)
```

---

## Pricing Notes

| Provider | Free Tier | Pay-As-You-Go | Best For |
|----------|-----------|---------------|----------|
| **Gemini** | Yes (limited) | $0.075/1M tokens | General queries |
| **Sunbird** | Yes (trial) | ~$0.05-0.15/1K tokens | African languages, voice |
| **Cerebras** | Yes (trial) | ~$0.5/1M tokens | High-volume, fast inference |

For an educational platform, start with **Gemini + Sunbird free tier**. You'll likely stay within free limits.

---

## Troubleshooting

### Q: Keys are set but still seeing only Gemini?
**A:** 
- Verify keys in Koyeb Dashboard (copy/paste to check)
- Check for leading/trailing spaces
- Redeploy the service
- Wait 5 minutes for cache flush

### Q: Getting "API key is missing" errors?
**A:**
- Verify the exact key format matches what the provider gives you
- Check for typos in environment variable names (case-sensitive)
- Ensure no spaces in keys

### Q: Sunbird/Cerebras returns error but Gemini works?
**A:**
- Verify the API URL is correct (copy from provider docs)
- Check your API key is still valid (might have expired)
- Some providers require specific request format - contact their support

### Q: How do I test locally?
**A:**
Create a `.env` file locally:
```
GEMINI_API_KEY=...
SUNBIRD_API_KEY=...
SUNBIRD_API_URL=...
```

Then test:
```python
from aiapp.ai_providers import route_ai_request

result = route_ai_request({
    'contents': [{'role': 'user', 'parts': [{'text': 'Hello'}]}],
    'language_code': 'sw'  # Test Swahili to prefer Sunbird
})

print(result['provider'])  # Should print: sunbird
```

---

## Next Steps

1. **Sign up for Sunbird** (recommended): https://www.sunbird.ai/
2. **Get your API key** and copy it
3. **Add to Koyeb** via Dashboard → Settings → Environment
4. **Redeploy** and wait 3 minutes
5. **Verify** by checking logs for provider switch

Once configured, your app will automatically handle Gemini rate limits! 🚀

Questions? Check:
- Sunbird docs: https://docs.sunbird.ai/
- Cerebras docs: https://docs.cerebras.ai/
- Koyeb docs: https://docs.koyeb.com/
