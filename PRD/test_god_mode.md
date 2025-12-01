# God Mode + Dynamic Thinking Test Script

## Test Environment Setup

1. **Stop the server** (Ctrl+C if running)
2. **Clear cache** to start fresh:
   ```powershell
   Remove-Item backend\data\web_cache.json -ErrorAction SilentlyContinue
   ```
3. **Restart server**:
   ```powershell
   cd backend
   python server.py
   ```
4. **Open browser**: http://localhost:8000

---

## Test 1: Live Fetch + Dynamic Thinking

### Action:
Send this message in the chat:
```
Check this article: https://techcrunch.com/2024/01/15/openai-gpt-4-turbo/
```

### Expected Results:
1. **Dynamic Thinking Animation**:
   - Loading should show rotating messages:
     - "🧠 Searching Internal Memory..."
     - "🌐 Accessing Web Tools..."
     - "⚡ Fetching External Sources..."
     - "📑 Reading & Summarizing Content..."
     - "🤖 Generating Analysis..."
   - Messages should fade in/out every 2.5 seconds
   - Should cycle smoothly until response arrives

2. **God Mode Badge**:
   - Citation card appears below AI response
   - Shows: **🌐 LIVE FETCH** badge (red glow)
   - Response time: **> 1.5 seconds** (because scraping is slow)
   - Primary source: `techcrunch.com`

3. **Memory Toast**:
   - Toast notification slides in from top-right
   - Shows: "🧠 KNOWLEDGE PERMANENTLY STORED"
   - Fades out after 4 seconds

---

## Test 2: Cache Hit (Speed Test)

### Action:
Send this message immediately after Test 1:
```
What did that TechCrunch article say?
```

### Expected Results:
1. **Dynamic Thinking Animation**:
   - Should still show rotating status messages
   - Should be MUCH faster (< 1.5s)

2. **God Mode Badge**:
   - Citation card appears below AI response
   - Shows: **⚡ CACHE** badge (green glow)
   - Response time: **< 1.5 seconds** (instant from cache)
   - Primary source: `techcrunch.com`

3. **No Toast**:
   - No memory toast (already stored in Test 1)

---

## Test 3: Memory Recall (New Session)

### Action:
1. **Open new browser tab** or **clear chat history**
2. Send this message:
```
What was that article about OpenAI GPT-4 Turbo we discussed?
```

### Expected Results:
1. **Dynamic Thinking Animation**:
   - Shows rotating status messages
   - Faster than Test 1, slower than Test 2

2. **God Mode Badge**:
   - Citation card appears below AI response
   - Shows: **🧠 MEMORY** badge (cyan glow)
   - Response time: **~1-2 seconds** (from ChromaDB vector store)
   - Primary source: `techcrunch.com` (recalled from memory)

3. **No Toast**:
   - No toast (memory already exists)

---

## Test 4: Internal Knowledge (No RAG)

### Action:
Send this message:
```
What is Python?
```

### Expected Results:
1. **Dynamic Thinking Animation**:
   - Shows rotating status messages
   - Very fast (< 1s)

2. **God Mode Badge**:
   - Citation card appears below AI response
   - Shows: **🤖 INTERNAL KNOWLEDGE** badge (blue glow)
   - Response time: **< 0.5 seconds** (LLM only)
   - Primary source: `Groq AI` or `LLM Knowledge Base`

3. **No Toast**:
   - No toast (no external knowledge stored)

---

## Validation Checklist

### Dynamic Thinking (All Tests)
- [ ] Loading status messages rotate every 2.5 seconds
- [ ] Smooth fade-in/fade-out transitions
- [ ] Messages cycle through all 5 states
- [ ] Animation stops when response arrives
- [ ] No interval leaks (check browser console)

### God Mode Badges (Test-Specific)
- [ ] Test 1: 🌐 LIVE FETCH (red, > 1.5s)
- [ ] Test 2: ⚡ CACHE (green, < 1.5s)
- [ ] Test 3: 🧠 MEMORY (cyan, ~1-2s)
- [ ] Test 4: 🤖 INTERNAL (blue, < 0.5s)

### Memory Toast
- [ ] Test 1: Toast appears and says "🧠 KNOWLEDGE PERMANENTLY STORED"
- [ ] Toast slides in from right
- [ ] Toast fades out after 4 seconds
- [ ] No duplicate toasts

### Citation Card
- [ ] Card appears below AI message
- [ ] Badge color matches status
- [ ] Latency displayed correctly
- [ ] Primary source shown
- [ ] Card styling matches theme

---

## Troubleshooting

### If Dynamic Thinking doesn't work:
1. Check browser console for errors
2. Verify `Messages.thinkingInterval` is being set
3. Confirm `.thinking-status` element exists in DOM
4. Check that interval is cleared in `hideLoading()`

### If God Mode badges don't appear:
1. Check network tab for `meta` object in API response
2. Verify `Messages.renderGodModeArtifacts()` is called in chat.js
3. Check console.log for "God Mode Artifacts:" output
4. Confirm CSS loaded (check Elements tab)

### If memory toast doesn't show:
1. Check if `meta.memory_active: true` in API response
2. Verify `triggerMemoryToast()` is called
3. Check `#memory-toast-container` exists in DOM
4. Confirm CSS animations loaded

---

## Success Criteria

All tests pass if:
1. ✅ Dynamic Thinking shows all 5 rotating messages
2. ✅ All 4 badge types render correctly
3. ✅ Toast appears only on first external URL query
4. ✅ Latency numbers match expected ranges
5. ✅ No console errors
6. ✅ Animations are smooth and professional

---

## Performance Benchmarks

| Test | Expected Latency | Badge Type |
|------|-----------------|------------|
| Live Fetch | 2-5 seconds | 🌐 LIVE FETCH |
| Cache Hit | 0.3-1.5 seconds | ⚡ CACHE |
| Memory Recall | 1-2 seconds | 🧠 MEMORY |
| Internal Knowledge | 0.2-0.5 seconds | 🤖 INTERNAL |

---

## Notes

- **Why Test Order Matters**: Tests must run in sequence because Test 2 depends on Test 1's cache, and Test 3 depends on Test 1's memory storage.

- **Cache Location**: `backend/data/web_cache.json`

- **Memory Location**: `backend/data/chroma_db/` (ChromaDB vector store)

- **Clear Everything**:
  ```powershell
  Remove-Item backend\data\web_cache.json -ErrorAction SilentlyContinue
  Remove-Item backend\data\chroma_db -Recurse -Force -ErrorAction SilentlyContinue
  ```

