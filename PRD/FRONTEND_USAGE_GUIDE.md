# Frontend Usage Guide - Role Reversal UI

This guide shows you how to use the role reversal controls in the ATLAS web interface.

---

## Accessing the Interface

1. **Start the server**:
   ```bash
   cd backend
   python server.py
   ```

2. **Open your browser** and navigate to:
   ```
   http://localhost:8000/
   ```

3. **Scroll down** to see the **Role Reversal Controls** panel below the main search box.

---

## Role Reversal Controls Panel

The panel contains 3 main sections:

### 📝 Section 1: Role Configuration

```
┌─────────────────────────────────────────────────────────┐
│  Previous Role:  [proponent                   ]         │
│  Current Role:   [opponent                    ]         │
│                                                         │
│  System Prompt:  [You are now the opponent...  ]        │
│                                                         │
│  Current Task:   [Argue against renewable...   ]        │
└─────────────────────────────────────────────────────────┘
```

**Fields**:
- **Previous Role**: What role the agent was arguing (e.g., "proponent")
- **Current Role**: What role the agent is switching to (e.g., "opponent")
- **System Prompt**: Instructions for the agent in the new role
- **Current Task**: What the agent should do now

### 🎯 Section 2: Action Buttons

```
┌─────────────────────────────────────────────────────────┐
│  [ Build Reversal Context ]  [ Show Role History ]     │
│                                                          │
│  New Statement:  [Renewable energy is expensive...]     │
│  [ Check Consistency ]                                  │
└─────────────────────────────────────────────────────────┘
```

**Buttons**:
1. **Build Reversal Context**: Creates specialized context for role switch
2. **Show Role History**: Displays all arguments from the previous role
3. **Check Consistency**: Detects contradictions in new statements

### 📊 Section 3: Results Display

Results appear below the buttons in color-coded boxes:

```
┌─────────────────────────────────────────────────────────┐
│  ⚠️  POTENTIAL CONTRADICTIONS DETECTED                  │
│  Consistency Score: 0.65                                │
│  • Previously stated "cost-competitive with fossil..."  │
│  • Now claiming "NOT economically viable..."            │
└─────────────────────────────────────────────────────────┘
```

**Result Types**:
- 🟢 **Green boxes**: Success messages (no contradictions)
- 🟡 **Yellow boxes**: Warnings (potential contradictions)
- 🔴 **Red boxes**: Errors (API failures)

---

## Usage Examples

### Example 1: Build Role Reversal Context

**Scenario**: Agent was arguing FOR renewable energy, now must argue AGAINST it.

**Steps**:
1. Enter in fields:
   - Previous Role: `proponent`
   - Current Role: `opponent`
   - System Prompt: `You are now the opponent. Argue against renewable energy.`
   - Current Task: `Present your opening argument against renewable energy adoption.`

2. Click **"Build Reversal Context"**

3. **Result displayed**:
   ```
   ✅ Role Reversal Context Built
   
   Role Switch: proponent → opponent
   Previous Arguments Recalled: 5
   Token Estimate: ~782 tokens
   
   📄 Context Preview (click to expand)
   ▶ ZONE 1: SYSTEM PROMPT
      You are now the opponent. Argue against renewable energy.
      
   ▶ ZONE 2A: PREVIOUS ROLE ARGUMENTS
      As a proponent, you previously argued:
      1. Turn 1: Renewable energy reduces carbon emissions...
      2. Turn 2: Solar and wind are cost-competitive...
      ...
   ```

### Example 2: View Role History

**Scenario**: See all arguments made by the "proponent" role.

**Steps**:
1. Enter in field:
   - Previous Role: `proponent`

2. Click **"Show Role History"**

3. **Result displayed**:
   ```
   📜 Role History for "proponent" (5 memories)
   
   • Turn 1: Renewable energy significantly reduces carbon...
   • Turn 2: Solar and wind power are now cost-competitive...
   • Turn 3: Renewable energy creates more sustainable jobs...
   • Turn 4: Investment in renewables drives innovation...
   • Turn 5: Renewable energy provides energy independence...
   ```

### Example 3: Check for Contradictions

**Scenario**: Agent wants to say "Renewable energy is too expensive" but previously said it was "cost-competitive".

**Steps**:
1. Enter in fields:
   - Current Role: `proponent`
   - New Statement: `Renewable energy is NOT economically viable and is far more expensive than fossil fuels.`

2. Click **"Check Consistency"**

3. **Result displayed** (Warning):
   ```
   🔍 Consistency Check
   
   ⚠️ POTENTIAL CONTRADICTIONS DETECTED
   
   Consistency Score: 0.65
   
   • Potential contradiction with Turn 2: Previously stated
     "cost-competitive with fossil fuels", now claiming
     "NOT economically viable"
     
   Related Statements:
   • "Solar and wind power are now cost-competitive with
     fossil fuels in most regions." (score: 0.78)
   ```

---

## Color Coding

The UI uses color-coded alerts to quickly show result types:

### 🟢 Green (Success)
```
✅ No Contradictions Detected
Consistency Score: 0.95
```
- Statement is consistent with previous arguments
- No warnings generated

### 🟡 Yellow (Warning)
```
⚠️ Potential Contradictions Detected
Consistency Score: 0.65
• Previously stated X, now claiming Y...
```
- Potential contradiction found
- Review suggested

### 🔴 Red (Error)
```
❌ Error: Missing 'role' field
```
- API call failed
- Check input fields

---

## Tips & Best Practices

### ✅ DO:
- Fill in all required fields before clicking buttons
- Use descriptive role names (e.g., "proponent", "opponent", "moderator")
- Write clear system prompts explaining the new role
- Check consistency BEFORE sending statements to the agent
- Use role history to review previous arguments

### ❌ DON'T:
- Leave required fields empty (causes errors)
- Use very long statements in consistency check (may be slow)
- Spam buttons (wait for previous request to complete)

---

## Keyboard Shortcuts

- **Enter** in text fields: Submit form (same as clicking button)
- **Click summary**: Expand/collapse context preview

---

## Troubleshooting

### "❌ Network error: Failed to fetch"
**Problem**: Server not running or wrong URL
**Solution**: 
1. Check server is running: `cd backend && python server.py`
2. Verify URL: http://localhost:8000/
3. Check browser console for CORS errors

### "❌ Error: Missing 'role' field"
**Problem**: Required field left empty
**Solution**: Fill in all required fields before clicking button

### Results not showing
**Problem**: JavaScript error or old cache
**Solution**:
1. Open browser console (F12) and check for errors
2. Hard refresh: Ctrl+F5 (Windows) or Cmd+Shift+R (Mac)
3. Clear browser cache

### Loading forever
**Problem**: Server overloaded or endpoint error
**Solution**:
1. Check server terminal for error messages
2. Restart server: Ctrl+C, then `python server.py`
3. Try simpler query first

---

## Advanced Features

### Collapsible Context Preview

Click the summary line to expand/collapse full context:

```
📄 Context Preview (click to expand)  ◀ Click here
▼ [Shows full context when expanded]
```

### Scrolling Results

Results area is scrollable if content is long:

```
┌─────────────────────────────────────┐
│  Result 1...                        │ ↕
│  Result 2...                        │ Scroll
│  Result 3...                        │ ↕
└─────────────────────────────────────┘
```

---

## Integration with Chat

The role reversal controls work alongside the main ATLAS chat interface:

1. **Use chat normally** for debates
2. **Switch to role reversal panel** when agent needs to change roles
3. **Build context** with role reversal
4. **Return to chat** with new context applied

---

## API Behind the Scenes

When you click buttons, the frontend calls these APIs:

| Button | Endpoint | Method |
|--------|----------|--------|
| Build Reversal Context | `/memory/role/reversal` | POST |
| Show Role History | `/memory/role/history` | POST |
| Check Consistency | `/memory/consistency/check` | POST |

You can also call these directly with curl/Postman (see `backend/tests/curl_examples.txt`).

---

## Mobile/Responsive Design

The UI adapts to smaller screens:

**Desktop** (wide layout):
```
[ Previous Role: xxx ]  [ Current Role: xxx ]
```

**Mobile** (stacked layout):
```
[ Previous Role: xxx ]
[ Current Role: xxx ]
```

All buttons and fields remain fully functional on mobile devices.

---

## Example Workflow

Here's a complete workflow for testing role reversal:

### Step 1: Initialize Debate
1. Open http://localhost:8000/
2. Use main chat to start a debate on renewable energy
3. Agent argues as PROPONENT for 5 turns

### Step 2: Switch Roles
1. Scroll to Role Reversal Controls
2. Enter:
   - Previous: `proponent`
   - Current: `opponent`
   - Prompt: `You must now argue against renewable energy`
   - Task: `Present your first argument as opponent`
3. Click "Build Reversal Context"
4. Review the context showing previous PRO arguments

### Step 3: Check Consistency
1. Before agent speaks, enter potential new statement:
   - New Statement: `Renewable energy is too expensive`
2. Click "Check Consistency"
3. Review any warnings about contradicting previous stance

### Step 4: Continue Debate
1. If no contradictions, proceed with new statement
2. If contradictions found, revise statement
3. Return to main chat and continue debate

---

## Visual Reference

```
╔═══════════════════════════════════════════════════════════╗
║                    ATLAS Homepage                          ║
╠═══════════════════════════════════════════════════════════╣
║                                                            ║
║  [Search Box]                                              ║
║                                                            ║
║  ┌──────────────────────────────────────────────────┐     ║
║  │  Role Reversal Controls                          │     ║
║  ├──────────────────────────────────────────────────┤     ║
║  │  Previous Role: [____________]                   │     ║
║  │  Current Role:  [____________]                   │     ║
║  │                                                   │     ║
║  │  System Prompt: [__________________________]     │     ║
║  │                                                   │     ║
║  │  Current Task:  [__________________________]     │     ║
║  │                                                   │     ║
║  │  [Build Context]  [Show History]                │     ║
║  │                                                   │     ║
║  │  New Statement: [__________________________]     │     ║
║  │  [Check Consistency]                             │     ║
║  │                                                   │     ║
║  │  ┌─────────────────────────────────────────┐    │     ║
║  │  │  Results Display Area                   │    │     ║
║  │  │  (Shows context, history, or warnings)  │    │     ║
║  │  └─────────────────────────────────────────┘    │     ║
║  └──────────────────────────────────────────────────┘     ║
║                                                            ║
╚═══════════════════════════════════════════════════════════╝
```

---

**Happy Testing!** 🚀

For API documentation, see:
- `backend/tests/curl_examples.txt`
- `RAG_PRD/PHASE2_ROLE_REVERSAL.md`
- `INTEGRATION_COMPLETE.md`
