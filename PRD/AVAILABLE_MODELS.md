# ATLAS - Available AI Models

## ✅ Your Current Configuration

**Model:** `llama-3.1-8b-instant`  
**Status:** ✅ **VALID** - This model exists and works on Groq!  
**Problem:** Your Groq API key is invalid, not the model name.

---

## 🚀 Available Groq Models

### **🔥 Recommended for Chat (Fast & Free)**

| Model | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| `llama-3.1-8b-instant` ⭐ | ⚡⚡⚡ Very Fast | Good | **Your current choice** - Best for chat |
| `llama-3.3-70b-versatile` | ⚡⚡ Fast | Excellent | Latest model, most capable |
| `mixtral-8x7b-32768` | ⚡⚡ Fast | Very Good | Long context (32K tokens) |

### **📋 All Available Models**

#### **LLaMA 3.x Series** (Meta)
```
llama-3.1-8b-instant         ← Your current (8B params, fastest)
llama-3.1-70b-versatile      (70B params, powerful)
llama-3.2-1b-preview         (1B params, tiny & fast)
llama-3.2-3b-preview         (3B params, small & fast)
llama-3.2-11b-vision-preview (11B params, supports images)
llama-3.2-90b-vision-preview (90B params, best vision)
llama-3.3-70b-versatile      (70B params, latest & best)
```

#### **Mixtral Series** (Mistral AI)
```
mixtral-8x7b-32768           (Expert model, 32K context)
mixtral-8x7b-instruct-v0.1   (Instruction-tuned)
```

#### **Gemma Series** (Google)
```
gemma-7b-it                  (7B params, Google's model)
gemma2-9b-it                 (9B params, improved)
```

---

## 🔧 How to Change Models

### **Option 1: Edit `.env` file**
```env
SINGLE_MODEL=llama-3.1-8b-instant  # Current (fast)
# or
SINGLE_MODEL=llama-3.3-70b-versatile  # Latest (better quality)
```

### **Option 2: Edit `config.py`**
```python
DEFAULT_MODEL = "llama3"  # Uses llama-3.1-8b-instant
# or
DEFAULT_MODEL = "llama3-large"  # Uses llama-3.3-70b-versatile
```

---

## 🎯 Model Comparison

### **Speed vs Quality**

```
Fast (Good for Chat):
├─ llama-3.1-8b-instant      ⚡⚡⚡ (Current)
├─ llama-3.2-3b-preview      ⚡⚡⚡⚡
└─ mixtral-8x7b-32768        ⚡⚡

Balanced:
├─ llama-3.3-70b-versatile   ⚡⚡ ⭐ Recommended
└─ mixtral-8x7b-instruct     ⚡⚡

Quality (Slower):
└─ llama-3.2-90b-vision      ⚡ (Best quality)
```

### **Free Tier Limits (Groq)**

All models are **free** with rate limits:
- ✅ 30 requests/minute
- ✅ 6,000 requests/day
- ✅ 7,000 tokens/minute

---

## 🐛 Troubleshooting

### **"Invalid API Key" Error**
❌ Problem: Your Groq API key is expired/invalid  
✅ Solution: Get new key from https://console.groq.com/keys

### **"Model not found" Error**
❌ Problem: Typo in model name  
✅ Solution: Copy exact name from list above

### **"Rate limit exceeded" Error**
❌ Problem: Too many requests  
✅ Solution: Wait 60 seconds or system auto-switches to HuggingFace

---

## 💡 Recommendations

### **For Your Use Case (Chat/Misinformation Fighter):**

1. **🥇 Best Choice:** `llama-3.3-70b-versatile`
   - Latest model
   - Best reasoning
   - Still fast enough

2. **🥈 Current (Good):** `llama-3.1-8b-instant` ← You're using this
   - Fastest response
   - Good enough for chat
   - Free tier friendly

3. **🥉 Alternative:** `mixtral-8x7b-32768`
   - Long context window
   - Good for analysis
   - Balanced performance

---

## 🔄 How to Switch Models

### **Quick Test:**
```python
# In Python console
from groq import Groq
client = Groq(api_key="your_key")

# Test different models
models = [
    "llama-3.1-8b-instant",
    "llama-3.3-70b-versatile",
    "mixtral-8x7b-32768"
]

for model in models:
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": "Hi!"}]
    )
    print(f"{model}: {response.choices[0].message.content}")
```

---

## 📊 Current Status

✅ **Model Name:** VALID (`llama-3.1-8b-instant`)  
❌ **API Key:** INVALID (needs replacement)  
✅ **Fallback:** HuggingFace (working)  
✅ **Auto-Failover:** ENABLED  

---

## 🚀 Next Steps

1. **Get Valid Groq API Key:** https://console.groq.com/keys
2. **Update `.env`:**
   ```env
   GROQ_API_KEY=gsk_YourNewKeyHere
   ```
3. **Restart Server:**
   - Double-click `start_server.bat`
   - OR: `.\.venv\Scripts\python.exe server.py`
4. **Test:** http://127.0.0.1:5000/chat

---

**Your model choice is correct! You just need a valid API key.** 🎯

For more info: https://console.groq.com/docs/models
