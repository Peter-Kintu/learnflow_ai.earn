# Step-by-Step: Add Sunbird API to Koyeb (5 Minutes)

## Part 1: Get Sunbird API Key (2 minutes)

### Step 1.1: Visit Sunbird
- Go to https://www.sunbird.ai/
- Click "Get Started" (top right) or "Sign Up"

### Step 1.2: Create Account
- Enter your email
- Set password
- Verify email

### Step 1.3: Get API Key
- Log in to dashboard
- Look for "API Keys" or "Settings" → "API"
- Click "Create New Key" or "Generate Key"
- Copy the key (looks like: `sk_live_xxxxxxxxxxxxx`)

**You now have:**
```
SUNBIRD_API_KEY=sk_live_xxxxxxxxxxxxx
SUNBIRD_API_URL=https://api.sunbird.ai/v1/generate
SUNBIRD_TTS_URL=https://api.sunbird.ai/v1/tts
```

---

## Part 2: Add Keys to Koyeb (3 minutes)

### Step 2.1: Open Koyeb Dashboard
- Go to https://app.koyeb.com
- Log in with your account

### Step 2.2: Find Your Service
- You should see "nakintu-ai" or your service name
- Click it to open

### Step 2.3: Go to Environment Settings
- Look for tabs: **Overview** | **Logs** | **Settings** | **Details**
- Click **Settings** tab
- Scroll down to "Environment Variables" section
- Click "Edit" or "Edit Environment Variables" button

### Step 2.4: Add the Three Variables

**In the text area, add these three lines:**

```
SUNBIRD_API_URL=https://api.sunbird.ai/v1/generate
SUNBIRD_API_KEY=sk_live_xxxxxxxxxxxxx
SUNBIRD_TTS_URL=https://api.sunbird.ai/v1/tts
```

**Replace `sk_live_xxxxxxxxxxxxx` with your actual Sunbird key from Step 1.3**

### Step 2.5: Save
- Click **Save** button (bottom right)
- Koyeb will show: "Redeploying service..."

### Step 2.6: Wait for Redeployment
- Koyeb will automatically redeploy your app
- This takes **2-3 minutes**
- Status will change from "Updating" → "Running"

---

## Part 3: Verify It Works (30 seconds)

### Step 3.1: Check Logs
- In Koyeb, click **Logs** tab
- Make a request to your app (open it in browser)
- Look for logs mentioning provider:

**✅ SUCCESS - Look for:**
```
AI Request completed using provider: sunbird
Diagnostics: {'providers_tried': ['sunbird', 'gemini'], ...}
```

**❌ FAILURE - If you see:**
```
Diagnostics: {'provider_availability': {'sunbird': 'missing SUNBIRD_API_KEY'}}
```

Then the key wasn't picked up. Go back to Step 2.4 and check for:
- Extra spaces
- Typos in variable names (case-sensitive!)
- Make sure you used the correct key from Sunbird

---

## Optional: Add Cerebras Too (For Extra Redundancy)

If you want a second fallback:

### Get Cerebras Key:
1. Visit https://www.cerebras.ai/
2. Click "Sign Up"
3. Create account
4. Go to API settings
5. Generate API key

### Add to Koyeb:
In the Environment Variables, add these two extra lines:

```
CEREBRAS_API_URL=https://api.cerebras.ai/v1/models/llama-3.1-70b-instruct/completions
CEREBRAS_API_KEY=csk_live_xxxxxxxxxxxxx
```

Then click **Save** and wait for redeployment.

---

## Final Checklist

After setup, you should have:

- ✅ Gemini API key (already configured)
- ✅ Sunbird API key (just added)
- ✅ Service redeployed on Koyeb
- ✅ Logs showing `provider: sunbird`

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Still seeing "provider: fallback" | Wait 5 more minutes for cache to clear, then refresh logs |
| "missing SUNBIRD_API_KEY" in logs | Check for typos in key or variable name in Koyeb |
| Provider shows "unconfigured" | Make sure you clicked "Save" and waited for redeployment |
| Sunbird API returns 401 error | Your API key has expired; generate a new one from Sunbird dashboard |

---

## What Happens Now

**Before (Rate Limited):**
```
User makes request → Gemini (429 error) → Fallback message
```

**After (Auto Fallback):**
```
User makes request → Try Gemini → If 429 → Try Sunbird ✅ → Return response
```

Your users in Uganda, Kenya, Tanzania, etc. will now get **instant responses even when Gemini is overloaded!** 🚀

---

## Cost

- **Gemini:** Free tier (generous limits)
- **Sunbird:** Free tier (trial credits)
- **For your educational platform:** Usually **free**

You'll likely never hit paid tier for Nakintu AI traffic levels.

---

**Done!** Your app is now resilient to Gemini rate limits. ✅
