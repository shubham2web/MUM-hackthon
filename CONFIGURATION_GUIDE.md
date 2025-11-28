# 🔧 ATLAS Configuration Guide

## ⚠️ IMPORTANT: API Key Required!

Your ATLAS server is running but **cannot generate AI responses** because:
- ❌ The Groq API key is **invalid or expired**
- ❌ You need to get a **new free API key**

---

## 🚀 Quick Fix (5 minutes)

### Step 1: Get Your Free Groq API Key

1. **Go to:** https://console.groq.com/keys
2. **Sign up/Login** (free account, no credit card needed)
3. **Click:** "Create API Key"
4. **Copy** the new API key (starts with `gsk_...`)

### Step 2: Update Your .env File

1. Open: `backend\.env` file
2. Find the line: `GROQ_API_KEY=your_new_groq_api_key_here`
3. Replace `your_new_groq_api_key_here` with your actual key
4. Save the file

**Example:**
```env
GROQ_API_KEY=gsk_YourActualApiKeyHere123456789
```

### Step 3: Restart the Server

**Option A: Use the batch file**
- Double-click `start_server.bat`

**Option B: From terminal**
```bash
cd backend
.\.venv\Scripts\python.exe server.py
```

### Step 4: Test It!

1. Open: http://127.0.0.1:5000/chat
2. Ask a question
3. You should get a real AI response! 🎉

---

## 📝 Current Configuration Status

### ✅ Working:
- Server is running
- Web interface loads
- Evidence gathering works
- Database initialized

### ❌ Not Working:
- AI response generation (needs valid Groq API key)

### 📍 Files to Check:
- **API Keys:** `backend\.env`
- **Server Code:** `backend\server.py`
- **AI Agent:** `backend\ai_agent.py`

---

## 🔑 Alternative: Use HuggingFace (Backup)

If you don't want to use Groq, you can use HuggingFace instead:

1. **Get HF Token:** https://huggingface.co/settings/tokens
2. **Update .env:**
   ```env
   HF_TOKEN_1=hf_YourHuggingFaceTokenHere
   SINGLE_MODE=True
   SINGLE_PROVIDER=huggingface
   ```

---

## 🆘 Troubleshooting

### "Invalid API Key" Error
- ✅ Get a new key from https://console.groq.com/keys
- ✅ Make sure you copied the entire key (starts with `gsk_`)
- ✅ No spaces before/after the key in .env file
- ✅ Restart the server after updating

### "Connection Refused" Error
- ✅ Make sure server is running (look for "Running on http://127.0.0.1:5000")
- ✅ Use the batch file: `start_server.bat`
- ✅ Check if port 5000 is available: `netstat -ano | findstr :5000`

### Server Keeps Stopping
- ✅ Normal for development mode
- ✅ Just restart it when needed
- ✅ Use the batch file for easy restart

---

## 📞 Need Help?

1. Check the terminal/console for error messages
2. Look at the server logs (JSON format)
3. Open an issue: https://github.com/shubham2web/MUM-hackthon/issues

---

**Last Updated:** November 7, 2025
**Status:** ⚠️ Needs valid Groq API key
