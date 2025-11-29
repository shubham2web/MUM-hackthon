// Chat Module
const Chat = {
    currentMode: 'analytical',
    isProcessing: false,
    initialized: false, // Add flag to prevent duplicate initialization

    init() {
        if (this.initialized) return; // Prevent multiple initialization

        Messages.init('#chatMessages');
        this.setupEventListeners();

        // Check URL parameters first
        const urlParams = new URLSearchParams(window.location.search);
        const modeParam = urlParams.get('mode');

        // Also check sessionStorage for chatMode (from homepage)
        const storedMode = sessionStorage.getItem('chatMode');

        if (modeParam === 'debate' || storedMode === 'debate') {
            this.currentMode = 'debate';
        } else if (storedMode === 'simplified') {
            this.currentMode = 'simplified';
        } else {
            this.currentMode = 'analytical';
        }

        // Clear the stored mode after using
        sessionStorage.removeItem('chatMode');

        // Update page title based on mode
        const chatTitle = document.getElementById('chatTitle');
        if (chatTitle) {
            if (this.currentMode === 'debate') {
                chatTitle.textContent = '🎭 Atlas Debate Mode';
                chatTitle.classList.add('mode-debate');
                chatTitle.classList.remove('mode-chat');
            } else {
                chatTitle.textContent = '💬 Chat with Atlas';
                chatTitle.classList.add('mode-chat');
                chatTitle.classList.remove('mode-debate');
            }
        }

        // ===== HOMEPAGE QUERY HANDLING =====
        // Check if coming from homepage with a new query (forceNewChat flag)
        const forceNewChat = sessionStorage.getItem('forceNewChat');
        const initialPrompt = sessionStorage.getItem('initialPrompt');
        const ocrResults = sessionStorage.getItem('ocrResults');
        
        const messages = document.getElementById('chatMessages');
        
        // Log for debugging
        console.log('🔍 Chat.init() - forceNewChat:', forceNewChat);
        console.log('🔍 Chat.init() - initialPrompt:', initialPrompt);
        console.log('🔍 Chat.init() - ocrResults:', ocrResults ? 'present' : 'none');
        
        // CRITICAL: If we have an initialPrompt from homepage, ALWAYS start fresh
        // This handles both forceNewChat=true AND cases where flag wasn't set properly
        const hasHomepageQuery = (forceNewChat === 'true') || (initialPrompt && initialPrompt.length > 0);
        
        if (hasHomepageQuery) {
            console.log('🆕 HOMEPAGE QUERY DETECTED - Creating brand new chat session');
            
            // Clear ALL flags immediately
            sessionStorage.removeItem('forceNewChat');
            sessionStorage.removeItem('initialPrompt');
            sessionStorage.removeItem('ocrResults');
            
            // Clear the UI completely - remove all old messages
            if (messages) {
                messages.innerHTML = '';
                console.log('✅ Cleared all messages from UI');
            }
            
            // Reset ALL chat state to force creation of new chat
            if (typeof ChatStore !== 'undefined') {
                ChatStore.currentChatId = null;
                // Clear ALL mode mappings to prevent any old chat from loading
                ChatStore.currentChatIdByMode = {};
                localStorage.removeItem('chatIdsByMode');
                console.log('✅ Cleared all chat ID mappings');
            }
            
            // Now create new chat and process the query
            this.processHomepageQuery(initialPrompt, ocrResults);
            
        } else {
            // Normal flow - NO homepage query, restore per-mode chat if present
            console.log('📂 Normal flow - checking for existing chat');
            try {
                const mappedId = (typeof ChatStore !== 'undefined' && ChatStore.currentChatIdByMode) ? ChatStore.currentChatIdByMode[this.currentMode] : null;
                if (mappedId) {
                    // Attempt to open the mapped chat for this mode
                    try { 
                        ChatStore.openChat(mappedId); 
                        ChatStore.currentChatId = mappedId; 
                    } catch (e) { 
                        console.warn('Failed to open mapped chat', e); 
                        if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); } 
                    }
                } else {
                    if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); }
                }
            } catch (e) {
                if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); }
            }

            // Check for OCR result from sessionStorage (old single file format)
            const ocrResult = sessionStorage.getItem('ocrResult');
            if (ocrResult) {
                this.handleOCRResult(JSON.parse(ocrResult));
                sessionStorage.removeItem('ocrResult');
            }
        }

        // Update navigation active state
        document.querySelectorAll('.nav-item').forEach(nav => {
            const navMode = nav.getAttribute('data-mode');
            // Match debate mode, or match chat for analytical/simplified modes
            if (navMode === 'debate' && this.currentMode === 'debate') {
                nav.classList.add('active');
            } else if (navMode === 'chat' && this.currentMode !== 'debate') {
                nav.classList.add('active');
            } else {
                nav.classList.remove('active');
            }
        });

        this.initialized = true; // Mark as initialized
    },

    handleOCRResult(ocrData) {
        // Clear welcome message
        const messages = document.getElementById('chatMessages');
        if (messages) {
            messages.innerHTML = '';
        }

        // Add user message showing the image was uploaded
        Messages.addUserMessage(`📷 Uploaded image: ${ocrData.filename}`);

        // Add AI analysis if available
        if (ocrData.aiAnalysis) {
            setTimeout(() => {
                Messages.addAIMessage(ocrData.aiAnalysis);
            }, 500);
        }
    },

    async handleMultipleOCRResults(ocrResults) {
        // Clear welcome message
        const messages = document.getElementById('chatMessages');
        if (messages) {
            messages.innerHTML = '';
        }

        // Add user message showing files were uploaded
        const fileNames = ocrResults.map(r => r.filename).join(', ');
        Messages.addUserMessage(`📷 Uploaded ${ocrResults.length} image(s): ${fileNames}`);

        // Optionally, you could ask the AI to analyze all the extracted text together
        const allText = ocrResults.map(r => `From ${r.filename}: ${r.extractedText}`).join('\n\n');
        const initialPrompt = sessionStorage.getItem('initialPrompt');

        // Ensure we have an active chat to persist messages
        try {
            if (!ChatStore.currentChatId) {
                const titleCandidate = initialPrompt || (ocrResults[0] && ocrResults[0].filename) || 'New Chat';
                const title = (titleCandidate && titleCandidate.length > 40) ? titleCandidate.slice(0, 40) + '...' : titleCandidate;
                const created = await ChatStore.createChat(title);
                if (created && (created._id || created.id)) ChatStore.currentChatId = created._id || created.id;
            }
        } catch (e) { console.warn('Could not create chat for OCR results', e); }

        if (initialPrompt) {
            setTimeout(async () => {
                Messages.showLoading('Analyzing uploaded images with evidence gathering...');
                try {
                    // Process each image with scraper-enhanced analysis
                    for (let i = 0; i < ocrResults.length; i++) {
                        const ocrData = ocrResults[i];

                        // Create FormData for re-processing with scraper
                        // We'll use the extracted text to trigger scraper analysis
                        const analysisPrompt = `${initialPrompt}\n\nAnalyze this text extracted from ${ocrData.filename}:\n\n${ocrData.extractedText}`;

                        // Add user message for this uploaded file and persist it
                        try {
                            const userText = `Uploaded ${ocrData.filename}: ${ocrData.extractedText || ''}`;
                            Messages.addUserMessage(`📷 ${ocrData.filename}`);
                            if (ChatStore.currentChatId) await ChatStore.appendMessage(ChatStore.currentChatId, 'user', userText);
                        } catch (e) { console.warn('append user ocr failed before analysis', e); }

                        const response = await fetch('/chat', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-API-Key': API_KEY
                            },
                            body: JSON.stringify({
                                message: analysisPrompt,
                                mode: this.currentMode,
                                use_scraper: true  // Enable scraper for fact-checking
                            })
                        });

                        const data = await response.json();

                        if (i === 0) {
                            Messages.hideLoading();
                        }

                        if (data.analysis || data.result || data.answer) {
                            const aiMessage = data.analysis || data.result || data.answer;
                            const displayMsg = `**Analysis of "${ocrData.filename}" (${i + 1}/${ocrResults.length}):**\n\n${aiMessage}`;
                            Messages.addAIMessage(displayMsg);
                            // Persist assistant reply to chat store (best-effort)
                            try { if (ChatStore.currentChatId) await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', aiMessage); } catch (e) { console.warn('append assistant message failed', e); }
                        }


                        // Small delay between processing multiple files
                        if (i < ocrResults.length - 1) {
                            await new Promise(resolve => setTimeout(resolve, 1000));
                        }
                    }
                } catch (error) {
                    Messages.hideLoading();
                    Messages.addAIMessage('❌ Error analyzing images: ' + error.message);
                }
            }, ocrResults.length * 300 + 500);
        }
    },

    /**
     * Process a query coming from the homepage
     * Creates a brand new chat and sends the query
     */
    async processHomepageQuery(initialPrompt, ocrResultsJson) {
        console.log('🆕 processHomepageQuery called');
        console.log('📝 Initial prompt:', initialPrompt);
        console.log('📎 OCR results:', ocrResultsJson ? 'present' : 'none');
        
        // Parse OCR results if present
        let ocrResults = null;
        if (ocrResultsJson) {
            try {
                ocrResults = JSON.parse(ocrResultsJson);
            } catch (e) {
                console.warn('Failed to parse OCR results', e);
            }
        }
        
        // Generate chat title from prompt or first file
        let chatTitle = 'New Chat';
        if (initialPrompt && initialPrompt.length > 0) {
            chatTitle = initialPrompt.length > 40 ? initialPrompt.slice(0, 40) + '...' : initialPrompt;
        } else if (ocrResults && ocrResults.length > 0 && ocrResults[0].filename) {
            chatTitle = ocrResults[0].filename;
        }
        
        // Create new chat in the store FIRST
        try {
            if (typeof ChatStore !== 'undefined') {
                console.log('📝 Creating new chat with title:', chatTitle);
                const newChat = await ChatStore.createChat(chatTitle);
                if (newChat && (newChat._id || newChat.id)) {
                    ChatStore.currentChatId = newChat._id || newChat.id;
                    // Update the mode mapping
                    ChatStore.currentChatIdByMode[this.currentMode] = ChatStore.currentChatId;
                    localStorage.setItem('chatIdsByMode', JSON.stringify(ChatStore.currentChatIdByMode));
                    console.log('✅ New chat created with ID:', ChatStore.currentChatId);
                }
            }
        } catch (e) {
            console.warn('Failed to create new chat', e);
        }
        
        // Handle OCR files if present
        if (ocrResults && ocrResults.length > 0) {
            // Show files were uploaded
            const fileNames = ocrResults.map(r => r.filename).join(', ');
            Messages.addUserMessage(`📷 Uploaded ${ocrResults.length} file(s): ${fileNames}`);
            
            // If there's also a prompt, process with the prompt
            if (initialPrompt && initialPrompt.length > 0) {
                // Process OCR results with the prompt
                setTimeout(async () => {
                    Messages.showLoading('Analyzing uploaded files...');
                    try {
                        for (let i = 0; i < ocrResults.length; i++) {
                            const ocrData = ocrResults[i];
                            const analysisPrompt = `${initialPrompt}\n\nAnalyze this text extracted from ${ocrData.filename}:\n\n${ocrData.extractedText}`;
                            
                            // Persist user message
                            try {
                                if (ChatStore.currentChatId) {
                                    await ChatStore.appendMessage(ChatStore.currentChatId, 'user', `📷 ${ocrData.filename}: ${initialPrompt}`);
                                }
                            } catch (e) { console.warn('append user message failed', e); }
                            
                            const response = await fetch('/chat', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-API-Key': API_KEY
                                },
                                body: JSON.stringify({
                                    message: analysisPrompt,
                                    mode: this.currentMode,
                                    use_scraper: true
                                })
                            });
                            
                            const data = await response.json();
                            if (i === 0) Messages.hideLoading();
                            
                            if (data.analysis || data.result || data.answer) {
                                const aiMessage = data.analysis || data.result || data.answer;
                                Messages.addAIMessage(aiMessage);
                                try {
                                    if (ChatStore.currentChatId) {
                                        await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', aiMessage);
                                    }
                                } catch (e) { console.warn('append assistant message failed', e); }
                            }
                            
                            if (i < ocrResults.length - 1) {
                                await new Promise(resolve => setTimeout(resolve, 500));
                            }
                        }
                    } catch (error) {
                        Messages.hideLoading();
                        Messages.addAIMessage('❌ Error analyzing files: ' + error.message);
                    }
                }, 300);
            }
        } else if (initialPrompt && initialPrompt.length > 0) {
            // Just a text prompt - fill input and send
            const inputEl = document.getElementById('messageInput');
            if (inputEl) {
                inputEl.value = initialPrompt;
                // Give UI a moment to settle, then send
                setTimeout(() => {
                    try {
                        console.log('📤 Auto-sending query:', initialPrompt);
                        this.handleSend();
                    } catch (e) {
                        console.warn('Auto send failed', e);
                    }
                }, 300);
            }
        } else {
            // No prompt, no files - just show welcome
            this.addWelcomeMessage();
        }
    },

    // Legacy method - now calls processHomepageQuery
    async createNewChatFromHomepage(initialPrompt, ocrResultsJson) {
        return this.processHomepageQuery(initialPrompt, ocrResultsJson);
    },

    switchMode(mode) {
        this.currentMode = mode;

        const chatTitle = document.getElementById('chatTitle');
        if (chatTitle) {
            if (mode === 'debate') {
                chatTitle.textContent = '🎭 Atlas Debate Mode';
                chatTitle.classList.add('mode-debate');
                chatTitle.classList.remove('mode-chat');
            } else {
                chatTitle.textContent = '💬 Chat with Atlas';
                chatTitle.classList.add('mode-chat');
                chatTitle.classList.remove('mode-debate');
            }
        }

        // Update URL without reloading
        const url = new URL(window.location);
        if (mode === 'debate') {
            url.searchParams.set('mode', 'debate');
        } else {
            url.searchParams.delete('mode');
        }
        window.history.pushState({}, '', url);

        // Try to restore the chat for the selected mode; fallback to welcome
        const messages = document.getElementById('chatMessages');
        try {
            const mappedId = (typeof ChatStore !== 'undefined' && ChatStore.currentChatIdByMode) ? ChatStore.currentChatIdByMode[mode] : null;
            if (mappedId) {
                try { ChatStore.openChat(mappedId); ChatStore.currentChatId = mappedId; }
                catch (e) { console.warn('Failed to open chat for mode', e); if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); } }
            } else {
                if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); }
            }
        } catch (e) {
            if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); }
        }

        console.log(`✅ Switched to ${mode} mode`);
    },

    // Abort controller for canceling requests
    abortController: null,
    
    // Request ID to track which request is current (prevents stale responses)
    currentRequestId: null,

    // Show loading state - hide send button, show stop button
    showLoadingState() {
        const sendBtn = document.getElementById('sendBtn');
        const sendText = document.getElementById('sendText');
        const stopBtn = document.getElementById('stopBtn');
        
        if (sendBtn) sendBtn.style.display = 'none';
        if (sendText) sendText.style.display = 'none';
        if (stopBtn) stopBtn.style.display = 'flex';
    },

    // Hide loading state - show send button, hide stop button
    hideLoadingState() {
        const sendBtn = document.getElementById('sendBtn');
        const sendText = document.getElementById('sendText');
        const stopBtn = document.getElementById('stopBtn');
        
        if (sendBtn) sendBtn.style.display = 'flex';
        if (sendText) sendText.style.display = 'inline';
        if (stopBtn) stopBtn.style.display = 'none';
    },

    // Stop the current generation
    stopGeneration() {
        console.log('🛑 STOP GENERATION called - canceling request:', this.currentRequestId);
        
        // Abort any active fetch requests
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
        
        // Invalidate current request ID to ignore any stale responses
        this.currentRequestId = null;
        
        this.isProcessing = false;
        Messages.hideLoading();
        this.hideLoadingState();
        
        // Remove any "typing" or partial response messages
        const typingIndicators = document.querySelectorAll('.typing-indicator, .loading-message');
        typingIndicators.forEach(el => el.remove());
        
        Messages.addAIMessage('⏹️ Generation stopped by user.');
    },

    // ==================== THINKING UI HELPERS (Debate Mode) ====================
    
    /**
     * Create and show a thinking bubble for a single step.
     * Returns a Promise that resolves when the bubble times out.
     */
    showReasoningStep(stepData, container, duration = 1200) {
        return new Promise(resolve => {
            const bubble = document.createElement('div');
            bubble.className = 'thinking-bubble';

            bubble.innerHTML = `
                <div class="thinking-dots">
                    <span class="thinking-dot"></span>
                    <span class="thinking-dot"></span>
                    <span class="thinking-dot"></span>
                </div>
                <div class="thinking-text">${this.escapeHtmlForThinking(stepData.message)}</div>
            `;

            container.appendChild(bubble);
            container.scrollTop = container.scrollHeight;

            // Animate then fade
            setTimeout(() => {
                bubble.classList.add('fade-out');
                // Remove after fade completes
                setTimeout(() => {
                    bubble.remove();
                    resolve();
                }, 350);
            }, duration);
        });
    },

    /**
     * Play a full trace sequence one step after another.
     */
    async playDebateReasoning(trace, container, perStepMs = 1200) {
        if (!Array.isArray(trace) || trace.length === 0) return;
        for (const step of trace) {
            await this.showReasoningStep(step, container, perStepMs);
        }
    },

    /**
     * Safe HTML escape for thinking bubbles
     */
    escapeHtmlForThinking(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    },

    /**
     * Main entry point for debate flow with Gemini-style thinking.
     * Shows "Show thinking" dropdown first (with pro/opp/moderator scripts),
     * then the verdict OUTSIDE/AFTER the thinking block.
     */
    async startDebateFlow(apiResponse) {
        const container = document.getElementById('chatMessages') || document.getElementById('debate-output');
        if (!container) {
            console.error('No container found for debate flow');
            return;
        }

        console.log('🧠 startDebateFlow received:', apiResponse);

        // Store the response for later use
        window.lastDebateResponse = apiResponse;

        // Create the AI response container (like Gemini's response bubble)
        const responseContainer = document.createElement('div');
        responseContainer.className = 'message ai-message debate-response';
        container.appendChild(responseContainer);

        // === GEMINI-STYLE "SHOW THINKING" DROPDOWN ===
        // Contains: Proponent script, Opponent script, Moderator script
        const hasThinking = (apiResponse.pro) || (apiResponse.opp) || (apiResponse.verdict);
        
        if (hasThinking) {
            const thinkingSection = document.createElement('div');
            thinkingSection.className = 'gemini-thinking-section';
            
            // Build the dropdown content with agent scripts
            let dropdownContent = '';
            
            // Proponent reasoning/script
            if (apiResponse.pro) {
                const proSummary = apiResponse.pro.summary || (apiResponse.pro.arguments && apiResponse.pro.arguments.join(' ')) || 'Analyzing supporting evidence...';
                const proThinking = apiResponse.pro.thinking || '';
                dropdownContent += `
                    <div class="thinking-section-block">
                        <div class="section-title pro-title">Proponent Analysis</div>
                        <p class="section-content">${this.escapeHtmlForThinking(proSummary)}</p>
                        ${proThinking ? `<div class="section-reasoning">${this.escapeHtmlForThinking(proThinking)}</div>` : ''}
                    </div>
                `;
            }
            
            // Opponent reasoning/script
            if (apiResponse.opp) {
                const oppSummary = apiResponse.opp.summary || (apiResponse.opp.arguments && apiResponse.opp.arguments.join(' ')) || 'Analyzing counter-arguments...';
                const oppThinking = apiResponse.opp.thinking || '';
                dropdownContent += `
                    <div class="thinking-section-block">
                        <div class="section-title opp-title">Opponent Analysis</div>
                        <p class="section-content">${this.escapeHtmlForThinking(oppSummary)}</p>
                        ${oppThinking ? `<div class="section-reasoning">${this.escapeHtmlForThinking(oppThinking)}</div>` : ''}
                    </div>
                `;
            }
            
            // Moderator/Judge reasoning
            if (apiResponse.verdict && apiResponse.verdict.summary) {
                dropdownContent += `
                    <div class="thinking-section-block">
                        <div class="section-title moderator-title">Moderator Analysis</div>
                        <p class="section-content">${this.escapeHtmlForThinking(apiResponse.verdict.summary)}</p>
                    </div>
                `;
            }
            
            thinkingSection.innerHTML = `
                <div class="gemini-thinking-toggle">
                    <span class="thinking-sparkle-icon">✦</span>
                    <button class="show-thinking-btn">
                        Show thinking
                        <span class="chevron-icon">▲</span>
                    </button>
                </div>
                <div class="thinking-dropdown-content">
                    ${dropdownContent}
                </div>
            `;
            
            // Add click handler for the thinking toggle
            const toggleBtn = thinkingSection.querySelector('.show-thinking-btn');
            const dropdownDiv = thinkingSection.querySelector('.thinking-dropdown-content');
            if (toggleBtn && dropdownDiv) {
                toggleBtn.addEventListener('click', () => {
                    dropdownDiv.classList.toggle('expanded');
                    toggleBtn.classList.toggle('active');
                });
            }
            
            responseContainer.appendChild(thinkingSection);
        }

        // === VERDICT BOX (OUTSIDE/AFTER the thinking dropdown) ===
        // This is the main visible output like Gemini shows
        if (apiResponse.verdict) {
            const verdictBox = document.createElement('div');
            verdictBox.className = 'verdict-result-box';
            
            const verdict = apiResponse.verdict;
            const verdictText = verdict.verdict || 'INCONCLUSIVE';
            const confidence = verdict.confidence_pct || 50;
            const recommendation = verdict.recommendation || '';
            
            // Determine verdict color
            let verdictColor = '#FBBF24'; // yellow for complex/inconclusive
            if (verdictText === 'VERIFIED' || verdictText === 'TRUE') {
                verdictColor = '#10B981'; // green
            } else if (verdictText === 'DEBUNKED' || verdictText === 'FALSE') {
                verdictColor = '#EF4444'; // red
            }
            
            verdictBox.innerHTML = `
                <div class="verdict-header">
                    <span class="verdict-icon">⚖️</span>
                    <span class="verdict-label">Final Verdict</span>
                </div>
                <div class="verdict-main" style="color: ${verdictColor}">
                    ${verdictText}
                    <span class="verdict-confidence">${confidence}% confidence</span>
                </div>
                ${recommendation ? `<div class="verdict-recommendation">💡 ${this.escapeHtmlForThinking(recommendation)}</div>` : ''}
            `;
            
            responseContainer.appendChild(verdictBox);
        }

        // === 4-LINE REASONING SUMMARY ===
        if (apiResponse.explanation && apiResponse.explanation.summary_4_lines) {
            const lines = apiResponse.explanation.summary_4_lines;
            const reasoningBox = document.createElement('div');
            reasoningBox.className = 'reasoning-box';
            
            reasoningBox.innerHTML = `
                <h3 class="reasoning-title">🧠 How This Verdict Was Reached</h3>
                <ul class="reasoning-list">
                    <li>${this.escapeHtmlForThinking(lines[0])}</li>
                    <li>${this.escapeHtmlForThinking(lines[1])}</li>
                    <li>${this.escapeHtmlForThinking(lines[2])}</li>
                    <li>${this.escapeHtmlForThinking(lines[3])}</li>
                </ul>
                <details class="reasoning-details">
                    <summary>Show detailed reasoning</summary>
                    <pre class="reasoning-detailed">${this.escapeHtmlForThinking(apiResponse.explanation.detailed)}</pre>
                </details>
            `;
            
            responseContainer.appendChild(reasoningBox);
        }

        // === NLP EXPLANATION (More details) ===
        if (apiResponse.nlp_explanation) {
            const nlp = apiResponse.nlp_explanation;
            const nlpCard = document.createElement('div');
            nlpCard.className = 'nlp-explanation-card';
            
            const shortDiv = document.createElement('div');
            shortDiv.className = 'nlp-short';
            shortDiv.textContent = nlp.short || '';
            nlpCard.appendChild(shortDiv);
            
            if (nlp.detailed) {
                const toggleBtn = document.createElement('button');
                toggleBtn.className = 'nlp-toggle-btn';
                toggleBtn.textContent = 'More details';
                
                const detailsDiv = document.createElement('div');
                detailsDiv.className = 'nlp-details';
                detailsDiv.style.display = 'none';
                detailsDiv.textContent = nlp.detailed;
                
                toggleBtn.onclick = () => {
                    const isHidden = detailsDiv.style.display === 'none';
                    detailsDiv.style.display = isHidden ? 'block' : 'none';
                    toggleBtn.textContent = isHidden ? 'Hide details' : 'More details';
                    toggleBtn.classList.toggle('expanded', isHidden);
                };
                
                nlpCard.appendChild(toggleBtn);
                nlpCard.appendChild(detailsDiv);
            }
            
            responseContainer.appendChild(nlpCard);
        }

        // === EVIDENCE TILES ===
        // Only render evidence tiles in debate mode with verdict
        // This prevents duplicate evidence rendering
        if (apiResponse.evidence && apiResponse.evidence.length > 0 && apiResponse.verdict) {
            this.renderEvidenceTiles(apiResponse.evidence, responseContainer);
        }

        container.scrollTop = container.scrollHeight;
    },

    /**
     * Play animated thinking timeline (like ChatGPT/Gemini)
     */
    async playThinkingTimeline(trace, container) {
        for (const step of trace) {
            await this.showThinkingBubble(step, container);
        }
        // Add completion indicator
        const doneDiv = document.createElement('div');
        doneDiv.className = 'thinking-done';
        doneDiv.innerHTML = '✓ Thinking complete';
        container.appendChild(doneDiv);
    },

    /**
     * Show a single thinking bubble with animated dots
     */
    showThinkingBubble(step, container) {
        return new Promise(resolve => {
            const bubble = document.createElement('div');
            bubble.className = 'thinking-bubble';
            bubble.innerHTML = `
                <div class="thinking-dots">
                    <span></span><span></span><span></span>
                </div>
                <span class="thinking-text">${this.escapeHtmlForThinking(step.message)}</span>
            `;
            container.appendChild(bubble);
            container.scrollTop = container.scrollHeight;
            
            // Resolve after animation delay
            setTimeout(() => {
                bubble.classList.add('done');
                resolve();
            }, 1100);
        });
    },

    /**
     * Render Gemini-style "Show thinking" panel (kept for backwards compatibility)
     */
    renderThinkingPanel(apiResponse, container) {
        // This is now integrated into startDebateFlow
    },

    /**
     * Render proponent arguments box (clean, no inline thinking)
     */
    renderProponentBox(pro, container) {
        if (!pro) return;
        const box = document.createElement('div');
        box.className = 'message ai-message pro-box';
        
        const summary = pro.summary || (pro.arguments && pro.arguments.join(' • ')) || (pro.points && pro.points.join(' • ')) || 'No arguments available';
        
        box.innerHTML = `
            <div class="box-title pro-title">✅ Proponent</div>
            <div class="box-summary">${this.escapeHtmlForThinking(summary)}</div>
            ${pro.citations ? `<div class="box-citations">Citations: ${pro.citations.map(c => `[${c}]`).join(', ')}</div>` : ''}
        `;
        container.appendChild(box);
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Render opponent arguments box (clean, no inline thinking)
     */
    renderOpponentBox(opp, container) {
        if (!opp) return;
        const box = document.createElement('div');
        box.className = 'message ai-message opp-box';
        
        const summary = opp.summary || (opp.arguments && opp.arguments.join(' • ')) || (opp.points && opp.points.join(' • ')) || 'No arguments available';
        
        box.innerHTML = `
            <div class="box-title opp-title">❌ Opponent</div>
            <div class="box-summary">${this.escapeHtmlForThinking(summary)}</div>
            ${opp.citations ? `<div class="box-citations">Citations: ${opp.citations.map(c => `[${c}]`).join(', ')}</div>` : ''}
        `;
        container.appendChild(box);
        container.scrollTop = container.scrollHeight;
    },

    /**
     * Render safe background reasoning panel (PRD-compliant, no chain-of-thought)
     * Shows: pipeline trace, evidence provenance, agent summaries, score breakdown, audit fingerprint
     */
    renderBackgroundPanel(background, container) {
        if (!background) return;
        
        const panel = document.createElement('div');
        panel.className = 'bg-panel';

        const toggle = document.createElement('button');
        toggle.className = 'bg-toggle';
        toggle.innerHTML = '🔍 Show background reasoning';
        panel.appendChild(toggle);

        const inner = document.createElement('div');
        inner.className = 'bg-inner';
        inner.style.display = 'none';

        // Pipeline timeline
        if (background.trace && background.trace.length > 0) {
            const traceTitle = document.createElement('h4');
            traceTitle.textContent = '⏱️ Pipeline Timeline';
            inner.appendChild(traceTitle);
            
            background.trace.forEach(t => {
                const li = document.createElement('div');
                li.className = 'bg-trace';
                li.innerHTML = `<span class="trace-step">${this.escapeHtmlForThinking(t.step)}</span> — ${this.escapeHtmlForThinking(t.msg)} <span class="trace-time">(${t.took_ms} ms)</span>`;
                inner.appendChild(li);
            });
        }

        // Evidence provenance
        if (background.evidence_provenance && background.evidence_provenance.length > 0) {
            const evTitle = document.createElement('h4');
            evTitle.textContent = '📚 Evidence Provenance';
            inner.appendChild(evTitle);
            
            background.evidence_provenance.forEach(e => {
                const ev = document.createElement('div');
                ev.className = 'bg-evidence';
                const authorityPct = Math.round((e.authority || 0) * 100);
                const cacheIcon = e.cache_hit ? '💾' : '🌐';
                ev.innerHTML = `
                    <div class="bg-ev-header">
                        <span class="bg-ev-id">[${this.escapeHtmlForThinking(e.id)}]</span>
                        <strong>${this.escapeHtmlForThinking(e.title || e.domain)}</strong>
                        <span class="bg-ev-authority">Authority: ${authorityPct}%</span>
                        <span class="bg-ev-cache">${cacheIcon}</span>
                    </div>
                    <div class="bg-ev-meta">${this.escapeHtmlForThinking(e.domain)} · Method: ${this.escapeHtmlForThinking(e.method)}</div>
                    <div class="bg-ev-snippet">${this.escapeHtmlForThinking(e.snippet)}</div>
                `;
                inner.appendChild(ev);
            });
        }

        // Agent summaries
        if (background.agents && Object.keys(background.agents).length > 0) {
            const agTitle = document.createElement('h4');
            agTitle.textContent = '🤖 Agent Summaries';
            inner.appendChild(agTitle);
            
            Object.keys(background.agents).forEach(agentName => {
                const a = background.agents[agentName];
                const el = document.createElement('div');
                el.className = 'bg-agent';
                const usedEv = (a.used_evidence || []).join(', ') || 'none';
                el.innerHTML = `
                    <div class="bg-agent-name">${this.escapeHtmlForThinking(agentName)}</div>
                    <div class="bg-agent-summary">${this.escapeHtmlForThinking(a.summary || 'No summary')}</div>
                    <div class="bg-agent-evidence">Used evidence: ${usedEv}</div>
                `;
                inner.appendChild(el);
            });
        }

        // Score breakdown
        if (background.score_breakdown) {
            const scTitle = document.createElement('h4');
            scTitle.textContent = '📊 Score Breakdown';
            inner.appendChild(scTitle);
            
            const sb = background.score_breakdown;
            const sbEl = document.createElement('div');
            sbEl.className = 'bg-score';
            sbEl.innerHTML = `
                <div class="bg-score-row"><span>Combined Confidence:</span> <strong>${Math.round((sb.combined_confidence || 0) * 100)}%</strong></div>
                <div class="bg-score-row"><span>Authority Average:</span> <strong>${Math.round((sb.authority_avg || 0) * 100)}%</strong></div>
                <div class="bg-score-row"><span>Evidence Count:</span> <strong>${sb.evidence_count || 0}</strong></div>
                <div class="bg-score-formula">Formula: ${this.escapeHtmlForThinking(sb.calculation || 'N/A')}</div>
            `;
            inner.appendChild(sbEl);
        }

        // Audit fingerprint
        if (background.audit) {
            const audit = document.createElement('div');
            audit.className = 'bg-audit';
            const hash = (background.audit.deterministic_hash || '').slice(0, 12);
            audit.innerHTML = `
                <span class="bg-audit-label">🔐 Audit:</span>
                <span class="bg-audit-hash">fingerprint: ${hash}...</span>
                <span class="bg-audit-version">version: ${this.escapeHtmlForThinking(background.audit.version || 'unknown')}</span>
            `;
            inner.appendChild(audit);
        }

        // Toggle functionality
        toggle.onclick = () => {
            if (inner.style.display === 'none') {
                inner.style.display = 'block';
                toggle.innerHTML = '🔍 Hide background reasoning';
            } else {
                inner.style.display = 'none';
                toggle.innerHTML = '🔍 Show background reasoning';
            }
        };

        panel.appendChild(inner);
        container.appendChild(panel);
        container.scrollTop = container.scrollHeight;
    },

    // ==================== END THINKING UI HELPERS ====================

    setupEventListeners() {
        const sendBtn = document.getElementById('sendBtn');
        const stopBtn = document.getElementById('stopBtn');
        const input = document.getElementById('messageInput');
        
        console.log('🔧 setupEventListeners - sendBtn:', !!sendBtn, 'stopBtn:', !!stopBtn, 'input:', !!input);

        sendBtn?.addEventListener('click', () => this.handleSend());
        stopBtn?.addEventListener('click', () => this.stopGeneration());
        input?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSend();
            }
        });

        // Wire microphone: prefer browser Web Speech API when available (no server keys required)
        const micBtn = document.getElementById('micBtn');
        if (micBtn) {
            micBtn.addEventListener('click', async (ev) => {
                ev.preventDefault();

                // If browser supports Web Speech API, use it for client-only recognition (no server/API key needed)
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
                if (SpeechRecognition) {
                    try {
                        // Toggle recognition on/off if already listening
                        if (this._recognition && this._recognitionListening) {
                            this.stopWebSpeechRecognition();
                            return;
                        }
                        await this.startWebSpeechRecognition(SpeechRecognition);
                        return;
                    } catch (err) {
                        console.warn('Web Speech API failed, falling back to MediaRecorder', err);
                        // fallthrough to MediaRecorder fallback
                    }
                }

                // Fallback: MediaRecorder flow (server-side transcription)
                if (!this.recordingModal) this.createRecordingModal();
                this.showRecordingModal();
                try {
                    await this.startMediaRecording();
                } catch (err) {
                    console.error('Failed to start recording', err);
                    this.hideRecordingModal();
                    // Use a more helpful permission-aware handler
                    try { this.handleMediaPermissionError(err); } catch (e) { alert('Could not start microphone recording: ' + (err && err.message ? err.message : err)); }
                }
            });
        }
    },

    /************************************************************************
     * Recording UI + MediaRecorder
     ************************************************************************/
    createRecordingModal() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay recording-modal';
        modal.innerHTML = `
            <div class="modal-content" role="dialog" aria-label="Recording">
                <h2 id="recordingTitle">Recording...</h2>
                <div id="recordingAnimation" style="margin:18px 0;"></div>
                <div style="display:flex; gap:10px; justify-content:center; margin-top:8px;">
                    <button id="stopRecordingBtn" class="input-btn">Stop</button>
                    <button id="cancelRecordingBtn" class="input-btn">Cancel</button>
                </div>
                <div id="recordingStatus" style="margin-top:12px; font-size:13px; color: #cbd5e1;">Listening...</div>
            </div>`;

        document.body.appendChild(modal);
        this.recordingModal = modal;

        // Simple animation: pulsing dot
        const anim = modal.querySelector('#recordingAnimation');
        anim.innerHTML = `<div class="rec-dot" style="width:18px;height:18px;border-radius:50%;background:#ff4d4d;margin:0 auto;box-shadow:0 0 12px rgba(255,77,77,0.6);"></div>`;

        modal.querySelector('#stopRecordingBtn').addEventListener('click', () => this.stopMediaRecording());
        modal.querySelector('#cancelRecordingBtn').addEventListener('click', () => {
            this.cancelRecording = true;
            this.stopMediaRecording();
        });
    },

    showRecordingModal() {
        if (!this.recordingModal) this.createRecordingModal();
        this.recordingModal.classList.add('active');
    },

    hideRecordingModal() {
        if (this.recordingModal) this.recordingModal.classList.remove('active');
    },

    /************************************************************************
     * Permission help modal + helpers
     ************************************************************************/
    handleMediaPermissionError(err) {
        // Normalize name
        const name = (err && err.name) ? err.name : null;

        if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
            // Show helpful modal guiding the user to enable microphone access
            this.showPermissionModal({
                title: 'Microphone access blocked',
                message: 'Microphone access was blocked by your browser or operating system. To record audio, please allow microphone access for this site and reload the page.',
                details: err && err.message ? err.message : 'Permission denied',
                reason: 'denied'
            });
            return;
        }

        if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
            this.showPermissionModal({
                title: 'No microphone detected',
                message: 'No microphone device was found. Please connect a microphone and ensure it is enabled in your OS settings.',
                details: err && err.message ? err.message : 'No microphone',
                reason: 'notfound'
            });
            return;
        }

        // Generic fallback: attempt to query permission state for more info
        this.checkMicrophonePermission().then(state => {
            if (state === 'denied') {
                this.showPermissionModal({
                    title: 'Microphone access blocked',
                    message: 'Your browser is blocking microphone access for this site. Please allow microphone access in Site Settings and reload.',
                    details: err && err.message ? err.message : 'Permission denied',
                    reason: 'denied'
                });
            } else if (state === 'prompt') {
                this.showPermissionModal({
                    title: 'Allow microphone access',
                    message: 'The browser may prompt you to allow microphone access. Please allow it and try again.',
                    details: err && err.message ? err.message : 'Permission prompt',
                    reason: 'prompt'
                });
            } else {
                // Unknown / other error
                this.showPermissionModal({
                    title: 'Could not start recording',
                    message: 'An unexpected error occurred while trying to start the microphone.',
                    details: (err && err.message) ? err.message : String(err),
                    reason: 'unknown'
                });
            }
        }).catch(() => {
            // If permissions API unavailable, show generic modal
            this.showPermissionModal({
                title: 'Microphone not available',
                message: 'Could not access the microphone. Check your browser and OS microphone permissions.',
                details: err && err.message ? err.message : 'Error',
                reason: 'unknown'
            });
        });
    },

    createPermissionModal() {
        if (this.permissionModal) return;
        const modal = document.createElement('div');
        modal.className = 'modal-overlay permission-modal';
        modal.innerHTML = `
            <div class="modal-content" role="dialog" aria-label="Microphone help">
                <h2 id="permissionTitle">Microphone access</h2>
                <div id="permissionMessage" style="margin:8px 0; color:#cbd5e1;"></div>
                <pre id="permissionDetails" style="white-space:pre-wrap; font-size:12px; color:#94a3b8; background:transparent; border:none;"></pre>
                <div style="display:flex; gap:8px; justify-content:center; margin-top:12px;">
                    <button id="permissionRetryBtn" class="input-btn">Retry</button>
                    <button id="permissionOpenSettingsBtn" class="input-btn">Open site settings</button>
                    <button id="permissionDiagBtn" class="input-btn">Diagnostics</button>
                    <button id="permissionCloseBtn" class="input-btn">Close</button>
                </div>
                <div style="margin-top:10px; font-size:13px; color:#9ca3af; text-align:left;">Tips:
                    <ul style="margin:6px 0 0 18px; padding:0; color:#9ca3af;">
                        <li>Reload the page after changing permissions.</li>
                        <li>Test in Incognito / Private mode to rule out extensions.</li>
                        <li>Check Windows Settings → Privacy → Microphone and allow apps to access it.</li>
                    </ul>
                </div>
            </div>`;

        document.body.appendChild(modal);
        this.permissionModal = modal;

        modal.querySelector('#permissionCloseBtn').addEventListener('click', () => this.hidePermissionModal());
        modal.querySelector('#permissionRetryBtn').addEventListener('click', async () => {
            this.hidePermissionModal();
            // Try to start recording again
            try { await this.startMediaRecording(); } catch (e) { this.handleMediaPermissionError(e); }
        });

        modal.querySelector('#permissionOpenSettingsBtn').addEventListener('click', () => {
            // Try to guide user to site settings; best-effort to open a helpful URL
            try {
                // Many browsers block chrome:// links; open WebRTC sample as alternative
                window.open('chrome://settings/content/microphone', '_blank');
            } catch (e) {
                try { window.open('about:preferences#privacy', '_blank'); } catch (e) { /* ignore */ }
            }
            // Also open a troubleshooting sample page
            window.open('https://webrtc.github.io/samples/src/content/getusermedia/', '_blank');
        });

        // Diagnostics: show enumerateDevices + permissions info
        modal.querySelector('#permissionDiagBtn').addEventListener('click', async () => {
            const detailsEl = modal.querySelector('#permissionDetails');
            detailsEl.textContent = 'Running diagnostics...';
            try {
                const perm = navigator.permissions && navigator.permissions.query ? await navigator.permissions.query({ name: 'microphone' }) : null;
                const permState = perm ? perm.state : 'unavailable';
                let devices = [];
                try { devices = await navigator.mediaDevices.enumerateDevices(); } catch (e) { devices = [{ error: String(e) }]; }

                const out = {
                    permissionState: permState,
                    userAgent: navigator.userAgent,
                    devices: devices.map(d => ({ kind: d.kind, label: d.label, deviceId: d.deviceId }))
                };
                detailsEl.textContent = JSON.stringify(out, null, 2);
            } catch (e) {
                detailsEl.textContent = 'Diagnostics failed: ' + (e && e.message ? e.message : String(e));
            }
        });
    },

    showPermissionModal({ title, message, details, reason } = {}) {
        if (!this.permissionModal) this.createPermissionModal();
        const modal = this.permissionModal;
        modal.querySelector('#permissionTitle').textContent = title || 'Microphone access';
        modal.querySelector('#permissionMessage').textContent = message || '';
        modal.querySelector('#permissionDetails').textContent = details || '';
        modal.classList.add('active');
        // Update a simple status from Permissions API
        this.checkMicrophonePermission().then(state => {
            const statusEl = modal.querySelector('#permissionMessage');
            if (state === 'denied') statusEl.textContent += ' (permission state: denied)';
            else if (state === 'granted') statusEl.textContent += ' (permission state: granted)';
            else if (state === 'prompt') statusEl.textContent += ' (permission state: prompt)';
        }).catch(() => {});
    },

    hidePermissionModal() {
        if (this.permissionModal) this.permissionModal.classList.remove('active');
    },

    async checkMicrophonePermission() {
        if (!navigator.permissions || !navigator.permissions.query) return null;
        try {
            const p = await navigator.permissions.query({ name: 'microphone' });
            return p.state; // 'granted' | 'denied' | 'prompt'
        } catch (e) {
            return null;
        }
    },

    async startMediaRecording() {
        // Reset any previous state
        this.cancelRecording = false;
        this.recordedChunks = [];

        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this._mediaStream = stream;

        // Setup MediaRecorder
        const options = { mimeType: 'audio/webm' };
        try {
            this.mediaRecorder = new MediaRecorder(stream, options);
        } catch (e) {
            // Fallback to default
            this.mediaRecorder = new MediaRecorder(stream);
        }

        this.mediaRecorder.ondataavailable = (ev) => {
            if (ev.data && ev.data.size > 0) this.recordedChunks.push(ev.data);
        };

        this.mediaRecorder.onstop = async () => {
            // Stop audio nodes if any
            try { if (this._audioContext) { this._audioContext.close(); this._audioContext = null; } } catch (e) {}

            this.hideRecordingModal();

            if (this.cancelRecording) {
                this.recordedChunks = [];
                return;
            }

            const blob = new Blob(this.recordedChunks, { type: this.recordedChunks[0]?.type || 'audio/webm' });
            try {
                const transcript = await this.sendAudioToServer(blob);
                const input = document.getElementById('messageInput');
                if (input && transcript) input.value = transcript;
            } catch (err) {
                console.error('Transcription failed', err);
                alert('Transcription failed: ' + (err.message || err));
            }
        };

        // Start recording
        this.mediaRecorder.start();

        // Start VAD (silence detection) to auto-stop
        this.startVAD(stream);
    },

    /************************************************************************
     * Web Speech API (client-only) recognition fallback
     * Uses browser speech recognition (no server/API key) when available.
     ************************************************************************/
    async startWebSpeechRecognition(SpeechRecognitionCtor) {
        if (this._recognition && this._recognitionListening) return;

        // Create recognition instance
        const recognition = new SpeechRecognitionCtor();
        recognition.lang = 'en-US';
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;

        this._recognition = recognition;
        this._recognitionListening = true;

        const input = document.getElementById('messageInput');
        let interimText = '';

        const micBtn = document.getElementById('micBtn');
        if (micBtn) micBtn.classList.add('listening');

        recognition.onresult = (event) => {
            let finalTranscript = '';
            interimText = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const res = event.results[i];
                if (res.isFinal) finalTranscript += res[0].transcript;
                else interimText += res[0].transcript;
            }
            if (input) input.value = (finalTranscript + ' ' + interimText).trim();
        };

        recognition.onerror = (ev) => {
            console.error('Speech recognition error', ev);
            this._recognitionListening = false;
            if (micBtn) micBtn.classList.remove('listening');
        };

        recognition.onend = () => {
            this._recognitionListening = false;
            if (micBtn) micBtn.classList.remove('listening');
            // leave final value in input
        };

        recognition.start();
    },

    stopWebSpeechRecognition() {
        if (!this._recognition) return;
        try {
            this._recognition.stop();
        } catch (e) { console.warn('recognition.stop failed', e); }
        this._recognitionListening = false;
        const micBtn = document.getElementById('micBtn');
        if (micBtn) micBtn.classList.remove('listening');
    },

    stopMediaRecording() {
        try {
            if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') this.mediaRecorder.stop();
        } catch (e) { console.warn('mediaRecorder.stop error', e); }
        try { if (this._mediaStream) { this._mediaStream.getTracks().forEach(t => t.stop()); this._mediaStream = null; } } catch (e) {}
        try { if (this._vadInterval) { clearInterval(this._vadInterval); this._vadInterval = null; } } catch (e) {}
    },

    startVAD(stream) {
        // Very small VAD implementation using WebAudio RMS
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this._audioContext = new AudioContext();
            const source = this._audioContext.createMediaStreamSource(stream);
            const analyser = this._audioContext.createAnalyser();
            analyser.fftSize = 2048;
            source.connect(analyser);

            const data = new Uint8Array(analyser.fftSize);
            const silenceThreshold = 6; // adjust (lower = more sensitive)
            let silentMs = 0;
            const checkInterval = 250; // ms

            this._vadInterval = setInterval(() => {
                analyser.getByteTimeDomainData(data);
                // compute RMS
                let sum = 0;
                for (let i = 0; i < data.length; i++) {
                    const v = (data[i] - 128) / 128;
                    sum += v * v;
                }
                const rms = Math.sqrt(sum / data.length);
                const db = 20 * Math.log10(rms + 1e-8);

                // Update UI status
                const statusEl = this.recordingModal ? this.recordingModal.querySelector('#recordingStatus') : null;
                if (statusEl) statusEl.textContent = `Listening... (level: ${Math.round(db)})`;

                if (rms < 0.01) {
                    silentMs += checkInterval;
                } else {
                    silentMs = 0;
                }

                // If silence for > 1400ms, stop automatically
                if (silentMs > 1400) {
                    this.stopMediaRecording();
                }
            }, checkInterval);
        } catch (e) {
            console.warn('VAD not available', e);
        }
    },

    async sendAudioToServer(blob) {
        const form = new FormData();
        form.append('audio', blob, 'recording.webm');

        // Include application API key header if available (server requires X-API-Key)
        const fetchOpts = {
            method: 'POST',
            body: form,
            headers: {}
        };
        try { if (typeof API_KEY !== 'undefined' && API_KEY) fetchOpts.headers['X-API-Key'] = API_KEY; } catch (e) {}

        const resp = await fetch('/transcribe', fetchOpts);

        if (!resp.ok) {
            // Try to parse server JSON for structured error
            const j = await resp.json().catch(() => null);
            if (resp.status === 401) {
                const serverMsg = (j && j.error) ? j.error : 'Unauthorized';
                throw new Error(`Unauthorized: ${serverMsg}. The server requires an application API key (X-API-Key) to use transcription.`);
            }
            throw new Error((j && j.error) ? j.error : `Server returned ${resp.status}`);
        }

        const data = await resp.json();
        if (data && data.success && data.transcript) return data.transcript;
        throw new Error('No transcript returned');
    },

    /**
     * Show combined user message with text and image attachment preview
     */
    async showCombinedUserMessage(text, files) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        
        let htmlContent = '';
        
        // Add text message if present
        if (text && text.length > 0) {
            htmlContent += `<div class="user-message-text">${this.escapeHtml(text)}</div>`;
        }
        
        // Add image previews
        for (const file of files) {
            const isImage = file.type && file.type.startsWith('image/');
            
            if (isImage) {
                const imageUrl = await this.fileToDataURL(file);
                const fileSize = (file.size / 1024).toFixed(1);
                htmlContent += `
                    <div class="user-attachment-preview">
                        <img src="${imageUrl}" alt="${file.name}" class="attachment-preview-img">
                        <div class="attachment-preview-info">
                            <span class="attachment-preview-name">${file.name}</span>
                            <span class="attachment-preview-size">Image • ${fileSize} KB</span>
                        </div>
                    </div>
                `;
            } else {
                const fileSize = (file.size / 1024).toFixed(1);
                htmlContent += `
                    <div class="user-attachment-preview">
                        <div class="attachment-preview-icon">📄</div>
                        <div class="attachment-preview-info">
                            <span class="attachment-preview-name">${file.name}</span>
                            <span class="attachment-preview-size">${fileSize} KB</span>
                        </div>
                    </div>
                `;
            }
        }
        
        messageDiv.innerHTML = htmlContent;
        
        // Add timestamp
        const timestamp = document.createElement('div');
        timestamp.className = 'message-time';
        timestamp.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        messageDiv.appendChild(timestamp);
        
        const chatMessages = document.getElementById('chatMessages');
        if (chatMessages) {
            chatMessages.appendChild(messageDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
        
        // Persist combined message
        try {
            if (ChatStore.currentChatId) {
                const persistText = text + (files.length > 0 ? ` [${files.length} file(s) attached]` : '');
                await ChatStore.appendMessage(ChatStore.currentChatId, 'user', persistText);
            }
        } catch (e) { console.warn('Failed to persist combined message', e); }
    },
    
    /**
     * Convert file to data URL
     */
    fileToDataURL(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = (e) => resolve(e.target.result);
            reader.onerror = () => reject(new Error('Failed to read file'));
            reader.readAsDataURL(file);
        });
    },
    
    /**
     * Escape HTML characters
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    /**
     * Process image with user's text as context
     */
    async processImageWithContext(file, userMessage) {
        console.log('🖼️ Processing image with context:', file.name, 'Message:', userMessage);
        
        try {
            const formData = new FormData();
            formData.append('image', file);
            formData.append('analyze', 'true');
            formData.append('use_scraper', 'true');
            // Pass user's message as the question/context for analysis
            if (userMessage && userMessage.length > 0) {
                formData.append('question', userMessage);
            }

            console.log('📤 Sending to OCR endpoint with user context...');

            const response = await fetch('http://127.0.0.1:8000/ocr_upload', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Server error: ' + response.status);
            }

            const result = await response.json();
            console.log('📊 OCR Result:', result);

            if (result.success) {
                const { ocr_result, ai_analysis, evidence_count, evidence_sources } = result;

                // Log OCR details
                console.log(`📝 OCR: ${ocr_result.word_count} words, ${ocr_result.confidence.toFixed(1)}% confidence`);

                // Show AI analysis with context
                if (ai_analysis) {
                    const contextNote = userMessage ? `\n\n*Analysis based on your question: "${userMessage}"*` : '';
                    Messages.addAIMessage(`**🔍 Analysis of "${file.name}":**\n\n${ai_analysis}${contextNote}`);
                    
                    if (ChatStore.currentChatId) {
                        await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', `Analysis of ${file.name}: ${ai_analysis}`);
                    }
                } else {
                    Messages.addAIMessage(`✅ Image processed but no specific analysis was generated.`);
                }

                // Show evidence sources if available
                if (evidence_sources && evidence_sources.length > 0) {
                    let evidenceMsg = `\n\n**📚 ${evidence_count} source(s) found:**\n`;
                    evidence_sources.slice(0, 3).forEach((src, idx) => {
                        evidenceMsg += `${idx + 1}. [${src.title || src.domain}](${src.url})\n`;
                    });
                    Messages.addAIMessage(evidenceMsg);
                }
            } else {
                Messages.addAIMessage(`❌ Failed to process image: ${result.error || 'Unknown error'}`);
            }

        } catch (error) {
            console.error('❌ Image processing error:', error);
            Messages.addAIMessage(`❌ Error processing image: ${error.message}`);
        }
    },
    
    /**
     * Process text file with user's text as context
     */
    async processTextFileWithContext(file, userMessage) {
        console.log('📄 Processing text file with context:', file.name);
        
        try {
            const textContent = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve(e.target.result);
                reader.onerror = () => reject(new Error('Failed to read file'));
                reader.readAsText(file);
            });

            const wordCount = textContent.split(/\s+/).filter(w => w.length > 0).length;
            
            // Create analysis prompt combining file content and user message
            const analysisPrompt = userMessage 
                ? `${userMessage}\n\nContent from file "${file.name}" (${wordCount} words):\n\n${textContent}`
                : `Analyze this content from "${file.name}":\n\n${textContent}`;
            
            // Send to chat API for analysis
            const response = await API.sendMessage(analysisPrompt, this.currentMode, []);
            
            if (response && (response.analysis || response.result || response.answer)) {
                const aiResponse = response.analysis || response.result || response.answer;
                Messages.addAIMessage(aiResponse);
                
                if (ChatStore.currentChatId) {
                    await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', aiResponse);
                }
            }
        } catch (error) {
            console.error('❌ Text file processing error:', error);
            Messages.addAIMessage(`❌ Error processing file: ${error.message}`);
        }
    },

    async handleSend() {
        const input = document.getElementById('messageInput');
        console.log('📤 handleSend called, input element:', !!input);
        const message = input?.value?.trim() || '';
        console.log('📝 Message to send:', message);

        if (!message || this.isProcessing) {
            console.log('⚠️ Skipping send - no message or already processing');
            return;
        }

        // Check if V2 enhanced analysis is enabled
        const v2Toggle = document.getElementById('v2Toggle');
        const isV2Enabled = v2Toggle?.checked || false;

        // If V2 is enabled, validate that message contains a URL
        if (isV2Enabled) {
            const urlPattern = /https?:\/\/[^\s]+/i;
            const hasLink = urlPattern.test(message);
            
            if (!hasLink) {
                // Show animated error message in chat
                this.showV2LinkRequiredMessage();
                return;
            }
        }

        this.isProcessing = true;
        input.value = '';
        
        // Show loading state (hide send button, show stop button)
        this.showLoadingState();
        
        // Create abort controller for this request
        this.abortController = new AbortController();
        
        // Generate unique request ID to track this specific request
        const requestId = 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        this.currentRequestId = requestId;
        console.log('🆔 New request started:', requestId);
        
        // Ensure we have a chat to append to. Create one if necessary.
        try {
            if (!ChatStore.currentChatId) {
                const title = message.length > 40 ? message.slice(0, 40) + '...' : message;
                const created = await ChatStore.createChat(title || 'New Chat');
                if (created && (created._id || created.id)) {
                    ChatStore.currentChatId = created._id || created.id;
                    await ChatStore.listChats();
                }
            }
        } catch (e) { console.warn('Could not create/open chat before send', e); }

        // Check if we have attached files
        const hasAttachments = Attachments.attachedFiles && Attachments.attachedFiles.length > 0;
        
        // Show combined user message (text + attachments)
        if (hasAttachments) {
            // Create combined message with image preview and text
            await this.showCombinedUserMessage(message, Attachments.attachedFiles);
        } else {
            // Just text message
            Messages.addUserMessage(message);
            // Persist the user message to the chat store (best-effort)
            try { if (ChatStore.currentChatId) ChatStore.appendMessage(ChatStore.currentChatId, 'user', message); } catch (e) { console.warn('append user message failed', e); }
        }

        // Process attached files WITH the user's message context
        if (hasAttachments) {
            const filesToProcess = [...Attachments.attachedFiles];
            
            // Clear attachment area UI and files array immediately
            Attachments.attachedFiles = [];
            const attachmentArea = document.getElementById('attachmentArea');
            if (attachmentArea) attachmentArea.innerHTML = '';
            
            Messages.showLoading('Processing attached file(s)...');

            for (let i = 0; i < filesToProcess.length; i++) {
                const file = filesToProcess[i];
                const fileName = file.name.toLowerCase();

                // Check if it's an image or text file
                const isImage = fileName.endsWith('.jpg') || fileName.endsWith('.jpeg') || fileName.endsWith('.png');
                const isTextFile = fileName.endsWith('.md') || fileName.endsWith('.txt');

                if (isImage) {
                    // Pass user's message as context for OCR analysis
                    await this.processImageWithContext(file, message);
                } else if (isTextFile) {
                    await this.processTextFileWithContext(file, message);
                }

                // Small delay between files
                if (i < filesToProcess.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 300));
                }
            }

            Messages.hideLoading();
            this.isProcessing = false;
            this.hideLoadingState();
            return;
        }

        Messages.showLoading();

        // Check v2 toggle state early to set appropriate timeout
        const v2EnabledForTimeout = document.getElementById('v2Toggle')?.checked || false;
        
        // Add timeout for the request:
        // - v2.0 analysis: 300 seconds (5 minutes) - more complex with role reversal
        // - Standard: 180 seconds (3 minutes) for OCR + AI analysis
        const timeoutMs = v2EnabledForTimeout ? 300000 : 180000;
        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Request timed out')), timeoutMs)
        );
        
        // Store abort signal for passing to API calls
        const abortSignal = this.abortController.signal;

            try {
                // Check v2 toggle state
                const v2Enabled = document.getElementById('v2Toggle')?.checked || false;
                console.log('Sending message:', message, 'Mode:', this.currentMode, 'V2 enabled:', v2Enabled, 'RequestId:', requestId);
                
                // Collect conversation history from chat messages
                const conversationHistory = this.getConversationHistory();
                
                let response;
                
                // DEBATE MODE: Use /rag/debate with thinking animation
                if (this.currentMode === 'debate') {
                    console.log('🎭 Running debate mode with thinking animation...');
                    response = await Promise.race([
                        API.sendMessage(message, 'debate', conversationHistory, abortSignal),
                        timeoutPromise
                    ]);
                    
                    // Check if request was cancelled while waiting
                    if (this.currentRequestId !== requestId) {
                        console.log('🛑 Request', requestId, 'was cancelled, ignoring response');
                        return;
                    }
                    
                    Messages.hideLoading();
                    
                    // Handle new debate response with trace (thinking animation)
                    if (response && response.isDebate) {
                        console.log('🧠 Starting debate flow with trace animation...', response);
                        await this.startDebateFlow(response);
                        
                        // Persist verdict summary
                        if (ChatStore.currentChatId && response.verdict) {
                            const summary = `Verdict: ${response.verdict.verdict} (${response.verdict.confidence_pct}%) - ${response.verdict.summary}`;
                            ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', summary);
                        }
                    }
                    // Handle legacy verdict response (v4.1 without trace)
                    else if (response && response.isVerdict && response.verdict) {
                        console.log('📊 Displaying neutral verdict (v4.1)...', response.verdict);
                        this.displayFinalVerdict(response.verdict);
                        
                        // Persist verdict summary
                        if (ChatStore.currentChatId) {
                            const summary = `Verdict: ${response.verdict.verdict} (${response.verdict.confidence_pct}%) - ${response.verdict.summary}`;
                            ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', summary);
                        }
                    }
                    // Legacy: Handle old SSE stream (backwards compatibility)
                    else if (response && response.isStream) {
                        await this.handleDebateStream(response.response, message, requestId);
                    } else {
                        Messages.addAIMessage('Error: Unexpected response format from analysis.');
                    }
                }
                // CHAT MODE: Use v2.0 if enabled, otherwise standard chat
                else {
                    if (v2Enabled && typeof ATLASv2 !== 'undefined') {
                        console.log('💎 Using v2.0 enhanced analysis...');
                        // Use v2.0 enhanced analysis - pass abort signal
                        response = await Promise.race([
                            ATLASv2.analyzeWithV2(message, {
                                num_agents: 4,
                                enable_reversal: true,
                                reversal_rounds: 1
                            }, abortSignal),
                            timeoutPromise
                        ]);
                        
                        // Check if request was cancelled while waiting
                        if (this.currentRequestId !== requestId) {
                            console.log('🛑 Request', requestId, 'was cancelled, ignoring v2 response');
                            return;
                        }
                        
                        console.log('Received v2.0 response:', response);
                        Messages.hideLoading();
                        
                        if (response.success && response.data) {
                            // Use V2UI to render enhanced response
                            const v2Card = V2UI.createV2ResponseCard(response.data);
                            this.addV2Card(v2Card);
                            // Persist the FULL v2 response data as JSON with marker for re-rendering
                            try {
                                const v2DataToStore = {
                                    __v2_dashboard__: true,
                                    data: response.data
                                };
                                if (ChatStore.currentChatId) {
                                    ChatStore.appendMessage(
                                        ChatStore.currentChatId, 
                                        'assistant', 
                                        JSON.stringify(v2DataToStore),
                                        { is_v2_dashboard: true }
                                    );
                                }
                            } catch (e) { console.warn('append v2 response failed', e); }
                        } else {
                            Messages.addAIMessage(response.error || 'v2.0 analysis failed. Please try again.');
                        }
                    } else {
                        console.log('💬 Using standard chat analysis...');
                        // Use standard v1.0 analysis - pass abort signal
                        response = await Promise.race([
                            API.sendMessage(message, 'analytical', conversationHistory, abortSignal),
                            timeoutPromise
                        ]);
                        
                        // Check if request was cancelled while waiting
                        if (this.currentRequestId !== requestId) {
                            console.log('🛑 Request', requestId, 'was cancelled, ignoring standard response');
                            return;
                        }
                        
                        console.log('Received response:', response);
                        Messages.hideLoading();
                        
                        // Regular chat response
                        const aiMessage = response.analysis || 
                                        response.result || 
                                        response.answer ||
                                        'No response received.';
                                        
                        Messages.addAIMessage(aiMessage);
                        // Persist assistant reply (best-effort)
                        try { if (ChatStore.currentChatId) ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', aiMessage); } catch (e) { console.warn('append assistant message failed', e); }
                    }
                }
                
            } catch (error) {
                Messages.hideLoading();
                
                // Check if this was an abort (user clicked stop)
                if (error.name === 'AbortError') {
                    console.log('🛑 Request aborted:', requestId);
                    // Already handled by stopGeneration()
                    return;
                }
                
                // Check if request was cancelled
                if (this.currentRequestId !== requestId) {
                    console.log('🛑 Request', requestId, 'was cancelled during error handling');
                    return;
                }
                
                if (error.message === 'Request timed out') {
                    const v2On = document.getElementById('v2Toggle')?.checked || false;
                    if (v2On) {
                        Messages.addAIMessage('⏱️ The v2.0 enhanced analysis took too long (API rate limits may have caused delays). Try disabling v2.0 for faster results, or try again in a minute.');
                    } else {
                        Messages.addAIMessage('⏱️ The request took too long. Please try a simpler question.');
                    }
                } else {
                    Messages.addAIMessage('❌ Error: ' + error.message);
                }
                
                console.error('Chat error:', error);
            } finally {
                this.isProcessing = false;
                this.hideLoadingState();
                this.abortController = null;
            }
        },

    async handleDebateStream(response, originalTopic, requestId = null) {
        console.log('📡 Handling debate stream... RequestId:', requestId);
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let currentRole = null;
        let currentContent = '';
        let messageDiv = null;
        let firstMessageReceived = false; // Track if we've received first message
        let allDebateContent = []; // Store all debate messages for persistence
        let debateMetadata = null; // Store debate metadata

        try {
            let currentEventType = null;  // Track current SSE event type
            
            while (true) {
                // Check if request was cancelled
                if (requestId && this.currentRequestId !== requestId) {
                    console.log('🛑 Debate stream cancelled for request:', requestId);
                    reader.cancel();
                    return;
                }
                
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    // Check again inside loop
                    if (requestId && this.currentRequestId !== requestId) {
                        console.log('🛑 Debate stream cancelled during chunk processing');
                        reader.cancel();
                        return;
                    }
                    
                    if (!line.trim() || line.startsWith(':')) continue;

                    // Track event type from SSE
                    if (line.startsWith('event: ')) {
                        currentEventType = line.substring(7).trim();
                        console.log('📨 SSE Event:', currentEventType);
                        continue;
                    }

                    if (line.startsWith('data: ')) {
                        const data = line.substring(6).trim();

                        if (data === '[DONE]') {
                            // Flush any remaining content
                            if (currentContent && messageDiv) {
                                messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                allDebateContent.push({ role: currentRole, content: currentContent });
                            }

                            // Persist the complete debate to chat store
                            if (ChatStore.currentChatId && allDebateContent.length > 0) {
                                const debateTranscript = allDebateContent.map(d =>
                                    `**${d.role.toUpperCase()}**: ${d.content}`
                                ).join('\n\n');
                                try {
                                    await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', debateTranscript);
                                } catch (e) { console.warn('Failed to persist debate', e); }
                            }

                            console.log('✅ Debate stream complete');
                            this.hideLoadingState();
                            currentEventType = null;
                            return;
                        }

                        try {
                            const json = JSON.parse(data);
                            
                            // 🎯 Handle METADATA event (debate ID, topic, etc.)
                            if (currentEventType === 'metadata' || json.debate_id) {
                                console.log('📋 Debate metadata received:', json);
                                this.displayDebateMetadata(json, () => {
                                    if (!firstMessageReceived) {
                                        Messages.hideLoading();
                                        firstMessageReceived = true;
                                    }
                                });
                                currentEventType = null;
                                continue;
                            }
                            
                            // 🎯 Handle FINAL VERDICT event
                            if (currentEventType === 'final_verdict' || json.verdict) {
                                console.log('⚖️ Final Verdict received:', json);
                                this.displayFinalVerdict(json);
                                currentEventType = null;
                                continue;
                            }
                            
                            // 📊 Handle analytics metrics event
                            if (currentEventType === 'analytics_metrics') {
                                console.log('📊 Analytics received:', json);
                                // Could display analytics summary here
                                currentEventType = null;
                                continue;
                            }
                            
                            // 🔄 Handle role reversal events
                            if (currentEventType === 'role_reversal_start') {
                                console.log('🔄 Role Reversal started');
                                this.displayRoleReversalNotice();
                                currentEventType = null;
                                continue;
                            }
                            
                            if (currentEventType === 'role_reversal_complete') {
                                console.log('🔄 Role Reversal complete:', json);
                                currentEventType = null;
                                continue;
                            }

                            // Handle "end" event - debate complete
                            if (json.message === "Debate complete." || currentEventType === 'end') {
                                // Ensure loading is hidden
                                Messages.hideLoading();

                                // Flush any remaining content
                                if (currentContent && messageDiv) {
                                    messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                    allDebateContent.push({ role: currentRole, content: currentContent });
                                }

                                // Persist the complete debate to chat store
                                if (ChatStore.currentChatId && allDebateContent.length > 0) {
                                    const debateTranscript = allDebateContent.map(d =>
                                        `**${d.role.toUpperCase()}**: ${d.content}`
                                    ).join('\n\n');
                                    try {
                                        await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', debateTranscript);
                                    } catch (e) { console.warn('Failed to persist debate', e); }
                                }

                                // Add completion message
                                const completionDiv = document.createElement('div');
                                completionDiv.className = 'message ai-message';
                                completionDiv.innerHTML = `
                                        <div style="text-align: center; padding: 20px; border: 2px solid #10b981; border-radius: 8px; background: rgba(16, 185, 129, 0.1);">
                                            <div style="font-size: 24px; margin-bottom: 10px;">✅</div>
                                            <div style="font-weight: 600; color: #10b981; margin-bottom: 5px;">Debate Complete</div>
                                            <div style="color: #6b7280; font-size: 14px;">The moderator has provided the final synthesis above.</div>
                                        </div>
                                    `;
                                Messages.container.appendChild(completionDiv);
                                Messages.container.scrollTop = Messages.container.scrollHeight;
                                console.log('✅ Debate completed successfully');
                                currentEventType = null;
                                return;
                            }

                            // Check for role change
                            if (json.role && json.role !== currentRole) {
                                // Hide loading indicator on first message
                                if (!firstMessageReceived) {
                                    console.log('🎯 First debate message received, hiding loading...');
                                    Messages.hideLoading();
                                    firstMessageReceived = true;
                                }

                                // Flush previous content
                                if (currentContent && messageDiv) {
                                    messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                    allDebateContent.push({ role: currentRole, content: currentContent });
                                }

                                // Start new message
                                currentRole = json.role;
                                currentContent = '';
                                messageDiv = this.createDebateMessage(currentRole);
                            }

                            // Append content (backend sends "text" not "content")
                            if (json.text || json.content) {
                                currentContent += (json.text || json.content);
                                if (messageDiv) {
                                    messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                }
                            }
                            
                            // Handle turn_error events - log but continue
                            if (currentEventType === 'turn_error' || json.message?.includes('error') || json.message?.includes('Error')) {
                                console.warn('⚠️ Turn error detected:', json);
                                // Don't stop the debate, just log the error
                                if (messageDiv && currentRole) {
                                    const errorText = json.message || 'An error occurred during this turn';
                                    currentContent += `\n\n⚠️ [System: ${errorText}]`;
                                    messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                }
                                currentEventType = null;
                                continue;
                            }

                        } catch (e) {
                            console.error('Error parsing SSE data:', e, data);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error in debate stream:', error);
            Messages.hideLoading(); // Hide loading on error
            this.hideLoadingState(); // Also hide the loading button state
            Messages.addAIMessage('❌ Error streaming debate: ' + error.message);
        }
    },

    createDebateMessage(role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        Messages.container.appendChild(messageDiv);
        Messages.container.scrollTop = Messages.container.scrollHeight;
        return messageDiv;
    },
    
    /**
     * Display debate metadata (ID, topic, etc.) at the start
     */
    displayDebateMetadata(metadata, hideLoadingCallback) {
        this.debateMetadata = metadata; // Store for later use
        const { debate_id, topic, model_used, memory_enabled, v2_features_enabled } = metadata;
        
        const metadataDiv = document.createElement('div');
        metadataDiv.className = 'message ai-message';
        metadataDiv.style.cssText = `
            background: rgba(66, 181, 235, 0.1);
            border-left: 3px solid #42b5eb;
            padding: 16px;
            margin-bottom: 16px;
            border-radius: 8px;
        `;
        
        let html = '<div style="font-size: 12px; color: rgba(255,255,255,0.7);">';
        if (debate_id) {
            html += `<div style="margin-bottom: 6px;"><strong>Debate ID:</strong> <code style="background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px; font-family: monospace;">${debate_id}</code></div>`;
        }
        if (topic) {
            html += `<div style="margin-bottom: 6px;"><strong>Topic:</strong> ${topic}</div>`;
        }
        if (model_used) {
            html += `<div style="margin-bottom: 6px;"><strong>Model:</strong> ${model_used}</div>`;
        }
        if (v2_features_enabled) {
            html += `<div style="color: #10b981; margin-top: 8px;">✨ v2.0 Enhanced Features Enabled</div>`;
        }
        html += '</div>';
        
        metadataDiv.innerHTML = html;
        Messages.container.appendChild(metadataDiv);
        Messages.container.scrollTop = Messages.container.scrollHeight;
        
        // Hide loading on first metadata
        if (hideLoadingCallback) {
            hideLoadingCallback();
        }
    },
    
    /**
     * Display the final verdict from neutral verdict engine (ATLAS v4.1)
     * 
     * Expected schema:
     * {
     *   verdict: "VERIFIED" | "DEBUNKED" | "COMPLEX",
     *   confidence: 0-1,
     *   confidence_pct: 0-100,
     *   summary: "...",
     *   key_evidence: [{title, url, snippet, authority}, ...],
     *   forensic_dossier: {entities: [{name, reputation_score, red_flags}, ...]},
     *   bias_signals: [{type, severity, explanation}, ...],
     *   recommendation: "...",
     *   contradictions: [...],
     *   timestamp: "..."
     * }
     */
    
    /**
     * Insert citation anchors into text, replacing [1], [2] with clickable links.
     * @param {string} text - Text containing citation markers like [1], [2]
     * @param {Array} evidenceBundle - Array of evidence objects with url property
     * @returns {string} HTML string with citation links
     */
    injectCitationAnchors(text, evidenceBundle) {
        if (!text || !evidenceBundle) return text || '';
        
        return text.replace(/\[(\d+)\]/g, (match, num) => {
            const idx = parseInt(num, 10) - 1;
            if (idx < 0 || idx >= evidenceBundle.length) return match;
            
            const ev = evidenceBundle[idx];
            const url = ev.url || '#';
            const hasValidUrl = url && url.startsWith('http');
            
            if (hasValidUrl) {
                return `<a href="${url}" target="_blank" rel="noreferrer noopener" class="citation-link" style="color: #60a5fa; text-decoration: none; font-weight: 600;">[${num}]</a>`;
            }
            return `<span class="citation-ref" style="color: #60a5fa; font-weight: 600;">[${num}]</span>`;
        });
    },
    
    /**
     * Render evidence tiles with citation markers.
     * Creates clickable evidence cards with [1], [2], etc. markers.
     */
    renderEvidenceTiles(evidenceBundle, containerEl) {
        if (!Array.isArray(evidenceBundle) || evidenceBundle.length === 0) return;
        
        const list = document.createElement('ul');
        list.className = 'evidence-list';
        list.style.cssText = 'list-style: none; padding: 0; margin: 0;';
        
        evidenceBundle.forEach((ev, idx) => {
            const citationIdx = ev.citation_idx || (idx + 1);
            const li = document.createElement('li');
            li.className = 'evidence-item';
            li.style.cssText = 'margin-bottom: 12px; padding: 12px; background: rgba(255,255,255,0.03); border-radius: 8px; border-left: 3px solid #60a5fa;';
            
            // Citation badge
            const cite = document.createElement('span');
            cite.className = 'evidence-cite';
            cite.style.cssText = 'display: inline-block; background: #60a5fa; color: #1a1a2e; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-right: 8px; font-size: 12px;';
            cite.textContent = `[${citationIdx}]`;
            
            // Title link
            const title = document.createElement('a');
            const url = ev.url || '#';
            const hasValidUrl = url && url.startsWith('http') && url.length >= 15;
            title.href = hasValidUrl ? url : '#';
            title.target = '_blank';
            title.rel = 'noreferrer noopener';
            title.style.cssText = 'color: #60a5fa; text-decoration: none; font-weight: 500;';
            title.textContent = ev.title || ev.domain || `Source ${citationIdx}`;
            if (!hasValidUrl) {
                title.style.cursor = 'default';
                title.onclick = (e) => e.preventDefault();
            }
            
            // Domain + authority meta
            const meta = document.createElement('div');
            meta.className = 'evidence-meta';
            meta.style.cssText = 'font-size: 12px; color: #9ca3af; margin-top: 4px;';
            const authorityPct = Math.round((ev.authority || 0.5) * 100);
            const sourceType = ev.source_type || 'Other';
            meta.textContent = `${ev.domain || ''} · ${sourceType} · Authority: ${authorityPct}%`;
            
            // Snippet (max 200 chars)
            const snip = document.createElement('div');
            snip.className = 'evidence-snippet';
            snip.style.cssText = 'font-size: 13px; color: #d1d5db; margin-top: 6px; line-height: 1.4;';
            const snippetText = ev.snippet || ev.summary || '';
            snip.textContent = snippetText.slice(0, 200) + (snippetText.length > 200 ? '...' : '');
            
            li.appendChild(cite);
            li.appendChild(title);
            li.appendChild(meta);
            li.appendChild(snip);
            list.appendChild(li);
        });
        
        containerEl.appendChild(list);
    },
    
    displayFinalVerdict(verdictObj) {
        // Extract verdict data
        const verdict = (verdictObj.verdict || 'COMPLEX').toUpperCase();
        const confidencePct = verdictObj.confidence_pct || Math.round((verdictObj.confidence || 0.5) * 100);
        const summary = verdictObj.summary || 'No summary available.';
        const keyEvidence = verdictObj.key_evidence || [];
        const forensicDossier = verdictObj.forensic_dossier || {entities: []};
        const biasSignals = verdictObj.bias_signals || [];
        const recommendation = verdictObj.recommendation || '';
        const contradictions = verdictObj.contradictions || [];
        
        // Determine verdict styling
        let verdictColor, verdictIcon, verdictBg;
        switch(verdict) {
            case 'VERIFIED':
                verdictColor = '#1FB65B';
                verdictIcon = '✅';
                verdictBg = 'rgba(31, 182, 91, 0.1)';
                break;
            case 'DEBUNKED':
                verdictColor = '#FF4D4F';
                verdictIcon = '❌';
                verdictBg = 'rgba(255, 77, 79, 0.1)';
                break;
            case 'COMPLEX':
            default:
                verdictColor = '#F2B705';
                verdictIcon = '⚖️';
                verdictBg = 'rgba(242, 183, 5, 0.1)';
        }
        
        // Build key evidence HTML with citation indices [1], [2], etc.
        let evidenceHtml = '';
        if (keyEvidence.length > 0) {
            const evidenceItems = keyEvidence.slice(0, 5)
                .filter(e => {
                    // Filter out malformed URLs like "https://www" without actual domain
                    const url = e.url;
                    if (!url) return true; // Allow entries without URL
                    if (!url.startsWith('http://') && !url.startsWith('https://')) return false;
                    if (url.length < 15) return false; // Too short to be valid
                    if (url === 'https://www' || url === 'http://www') return false;
                    return true;
                })
                .map((e, idx) => {
                const citationIdx = e.citation_idx || (idx + 1);
                const authority = e.authority ? Math.round(e.authority * 100) : 50;
                const title = e.title || e.source_id || 'Unknown Source';
                const url = e.url;
                const domain = e.domain || '';
                const sourceType = e.source_type || '';
                const snippet = (e.snippet || e.summary || '').slice(0, 150);
                const hasValidUrl = url && url.startsWith('http') && url.length >= 15;
                
                // Render title as link if URL is valid
                const titleHtml = hasValidUrl 
                    ? `<a href="${url}" target="_blank" rel="noreferrer noopener" style="color: #60a5fa; text-decoration: none; font-weight: 500;">${title}</a>`
                    : `<span style="color: #60a5fa; font-weight: 500;">${title}</span>`;
                
                return `
                    <li style="margin-bottom: 12px; padding: 10px; background: rgba(255,255,255,0.03); border-radius: 8px; border-left: 3px solid #60a5fa;">
                        <span style="display: inline-block; background: #60a5fa; color: #1a1a2e; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-right: 8px; font-size: 12px;">[${citationIdx}]</span>
                        ${titleHtml}
                        <div style="font-size: 12px; color: #9ca3af; margin-top: 4px;">${domain}${sourceType ? ' · ' + sourceType : ''} · Authority: ${authority}%</div>
                        ${snippet ? `<div style="font-size: 13px; color: #d1d5db; margin-top: 6px; line-height: 1.4;">${snippet}...</div>` : ''}
                    </li>
                `;
            }).join('');
            
            evidenceHtml = `
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <h4 style="font-weight: 600; margin-bottom: 12px; color: #e5e7eb;">📚 Key Evidence</h4>
                    <ul style="margin: 0; padding: 0; list-style: none; color: #d1d5db;">
                        ${evidenceItems}
                    </ul>
                </div>
            `;
        }
        
        // Build forensic dossier HTML
        let forensicHtml = '';
        if (forensicDossier.entities && forensicDossier.entities.length > 0) {
            const entityItems = forensicDossier.entities.slice(0, 3).map(entity => {
                const reputation = entity.reputation_score ? Math.round(entity.reputation_score * 100) : 50;
                const redFlagsText = entity.red_flags && entity.red_flags.length > 0 
                    ? `<div style="color: #fca5a5; font-size: 11px; margin-top: 4px;">Flags: ${entity.red_flags.join(', ')}</div>`
                    : '';
                return `
                    <div style="margin-bottom: 8px; padding: 8px; background: rgba(255,255,255,0.02); border-radius: 6px;">
                        <strong style="color: #e5e7eb;">${entity.name}</strong>
                        <span style="color: #9ca3af; font-size: 12px; margin-left: 8px;">
                            — reputation: ${reputation}%
                        </span>
                        ${redFlagsText}
                    </div>
                `;
            }).join('');
            
            forensicHtml = `
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <h4 style="font-weight: 600; margin-bottom: 8px; color: #e5e7eb;">🔬 Forensic Dossier</h4>
                    ${entityItems}
                </div>
            `;
        } else {
            forensicHtml = `
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <h4 style="font-weight: 600; margin-bottom: 8px; color: #e5e7eb;">🔬 Forensic Dossier</h4>
                    <p style="color: #9ca3af; font-size: 13px;">No notable entities found.</p>
                </div>
            `;
        }
        
        // Build recommendation HTML
        let recommendationHtml = '';
        if (recommendation) {
            recommendationHtml = `
                <div style="margin-top: 15px; padding: 10px; background: rgba(96, 165, 250, 0.1); border-left: 3px solid #60a5fa; border-radius: 4px;">
                    <div style="font-weight: 600; color: #60a5fa; margin-bottom: 4px;">💡 Recommendation</div>
                    <div style="color: #e5e7eb; font-size: 14px;">${recommendation}</div>
                </div>
            `;
        }
        
        // Build final verdict card
        const verdictDiv = document.createElement('div');
        verdictDiv.className = 'message ai-message verdict-card';
        verdictDiv.innerHTML = `
            <div style="padding: 20px; border: 2px solid ${verdictColor}; border-radius: 12px; background: ${verdictBg};">
                <!-- Verdict Badge -->
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 15px;">
                    <span style="font-size: 32px;">${verdictIcon}</span>
                    <div>
                        <div style="font-size: 12px; text-transform: uppercase; color: #9ca3af; letter-spacing: 1px;">Final Verdict</div>
                        <div style="font-size: 24px; font-weight: 700; color: ${verdictColor};">${verdict}</div>
                    </div>
                    <div style="margin-left: auto; text-align: right;">
                        <div style="font-size: 11px; color: #9ca3af;">Confidence</div>
                        <div style="font-size: 20px; font-weight: 600; color: ${verdictColor};">${confidencePct}%</div>
                    </div>
                </div>
                
                <!-- Summary -->
                <div style="color: #e5e7eb; line-height: 1.6; margin-bottom: 12px;">
                    ${summary}
                </div>
                
                ${recommendationHtml}
                ${evidenceHtml}
                ${forensicHtml}
                
                <div style="margin-top: 15px; font-size: 11px; color: #6b7280; text-align: center;">
                    ⚖️ Neutral Verdict by ATLAS v4.1 Analysis Engine
                </div>
            </div>
        `;
        
        Messages.container.appendChild(verdictDiv);
        Messages.container.scrollTop = Messages.container.scrollHeight;
    },
    
    /**
     * Display notice when role reversal round starts
     */
    displayRoleReversalNotice() {
        const noticeDiv = document.createElement('div');
        noticeDiv.className = 'message ai-message';
        noticeDiv.innerHTML = `
            <div style="text-align: center; padding: 15px; border: 1px dashed #8b5cf6; border-radius: 8px; background: rgba(139, 92, 246, 0.1);">
                <div style="font-size: 20px; margin-bottom: 8px;">🔄</div>
                <div style="font-weight: 600; color: #8b5cf6;">Role Reversal Round</div>
                <div style="color: #9ca3af; font-size: 13px; margin-top: 4px;">
                    Debaters are now switching positions to stress-test their arguments
                </div>
            </div>
        `;
        Messages.container.appendChild(noticeDiv);
        Messages.container.scrollTop = Messages.container.scrollHeight;
    },

    formatDebateContent(content, role) {
        let icon, label, colorClass;

        if (role === 'proponent') {
            icon = '🔵';
            label = 'PROPONENT';
            colorClass = 'proponent';
        } else if (role === 'opponent') {
            icon = '🔴';
            label = 'OPPONENT';
            colorClass = 'opponent';
        } else if (role === 'moderator') {
            icon = '🎙️';
            label = 'MODERATOR';
            colorClass = 'moderator';
        } else {
            icon = '💬';
            label = role.toUpperCase();
            colorClass = 'default';
        }

        // Enhanced formatting for moderator messages with forensic dossier
        let formattedContent = this.markdownToHtml(content);
        
        // Highlight forensic dossier sections in moderator messages
        if (role === 'moderator') {
            // Format forensic dossier sections
            formattedContent = formattedContent
                .replace(/FORENSIC DOSSIER|Forensic Analysis|Key Entities|Red Flags/gi, (match) => {
                    return `<strong style="color: #a855f7; font-size: 14px;">${match}</strong>`;
                })
                .replace(/Debate ID:\s*([a-f0-9-]+)/gi, (match, id) => {
                    return `<div style="background: rgba(168, 85, 247, 0.1); padding: 8px; border-radius: 4px; margin: 8px 0;"><strong>Debate ID:</strong> <code style="background: rgba(0,0,0,0.3); padding: 2px 6px; border-radius: 4px;">${id}</code></div>`;
                })
                .replace(/Topic:\s*(.+?)(?:\n|$)/gi, (match, topic) => {
                    return `<div style="background: rgba(168, 85, 247, 0.1); padding: 8px; border-radius: 4px; margin: 8px 0;"><strong>Topic:</strong> ${topic}</div>`;
                })
                .replace(/Credibility:\s*(\d+)\/100/gi, (match, score) => {
                    const color = score >= 70 ? '#10b981' : score >= 50 ? '#f59e0b' : '#ef4444';
                    return `<span style="color: ${color}; font-weight: bold;">Credibility: ${score}/100</span>`;
                })
                .replace(/Red Flags:\s*(\d+)/gi, (match, count) => {
                    const color = count > 5 ? '#ef4444' : count > 2 ? '#f59e0b' : '#10b981';
                    return `<span style="color: ${color}; font-weight: bold;">Red Flags: ${count}</span>`;
                });
        }

        return `
                <div class="debate-message ${colorClass}">
                    <div class="debate-header">
                        <span class="debate-icon">${icon}</span>
                        <strong>${label}</strong>
                    </div>
                    <div class="debate-content">${formattedContent}</div>
                </div>
            `;
    },

    markdownToHtml(text) {
        // Basic markdown conversion
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
    },

    addWelcomeMessage() {
        let message;
        if (this.currentMode === 'debate') {
            message = "🎭 **Welcome to Debate Mode!**\n\nI'll analyze your topic by presenting arguments from both sides:\n• 🔵 **Proponent** - Arguments in favor\n• 🔴 **Opponent** - Counter-arguments\n• 🎙️ **Moderator** - Synthesis and balance\n\nAsk me to debate any topic!";
        } else {
            message = "👋 Hello! I'm **Atlas**, your misinformation fighter.\n\n💬 **Chat Mode**: I'll provide clear, factual analysis of your questions.\n\n💡 **Tip**: Toggle v2.0 for enhanced multi-perspective analysis, or switch to Debate mode for structured debates!";
        }
        Messages.addAIMessage(message);
    },

    addV2Card(cardContent) {
        // Add v2.0/v2.5 response card to messages
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message v2-message';
        messageDiv.style.background = 'transparent';
        messageDiv.style.padding = '0';
        messageDiv.style.margin = '8px 0';
        
        // Handle both DOM elements and HTML strings
        if (typeof cardContent === 'string') {
            messageDiv.innerHTML = cardContent;
        } else if (cardContent instanceof HTMLElement) {
            messageDiv.appendChild(cardContent);
        } else {
            messageDiv.innerHTML = String(cardContent);
        }
        
        Messages.container.appendChild(messageDiv);
        Messages.scrollToBottom();
    },

    getConversationHistory() {
        // Collect all user and AI messages from the chat for context
        const history = [];
        const messagesContainer = document.getElementById('chatMessages');
        if (!messagesContainer) return history;

        const messageElements = messagesContainer.querySelectorAll('.message');
        messageElements.forEach(msgEl => {
            const isUser = msgEl.classList.contains('user-message');
            const messageTextEl = msgEl.querySelector('.message-text');

            if (messageTextEl) {
                const text = messageTextEl.textContent.trim();
                // Skip empty messages, loading indicators, and system messages
                if (text && !msgEl.classList.contains('loading-message') && text.length > 0) {
                    history.push({
                        role: isUser ? 'user' : 'assistant',
                        content: text
                    });
                }
            }
        });

        // Limit history to last 10 messages to avoid token limits
        return history.slice(-10);
    },

    /**
     * Show animated message when V2 is enabled but no link is provided
     */
    showV2LinkRequiredMessage() {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message v2-link-required-message';
        messageDiv.innerHTML = `
            <div class="v2-link-error-card">
                <div class="v2-link-error-icon">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 8v4M12 16h.01"/>
                    </svg>
                </div>
                <div class="v2-link-error-content">
                    <div class="v2-link-error-title">🔗 Link Required for V2 Analysis</div>
                    <div class="v2-link-error-text">
                        <strong>ATLAS v2.5 Enhanced Analysis</strong> is designed to analyze web content and articles.
                    </div>
                    <div class="v2-link-error-details">
                        <div class="v2-link-error-item">
                            <span class="v2-error-icon">❌</span>
                            <span>Plain text cannot be processed in V2 mode</span>
                        </div>
                        <div class="v2-link-error-item">
                            <span class="v2-error-icon">✅</span>
                            <span>Paste a URL to analyze (e.g., news articles, blog posts)</span>
                        </div>
                    </div>
                    <div class="v2-link-error-hint">
                        💡 <em>Tip: Disable V2 Enhanced Analysis to chat with regular text queries</em>
                    </div>
                </div>
            </div>
        `;
        
        Messages.container.appendChild(messageDiv);
        Messages.scrollToBottom();
        
        // Add entrance animation
        requestAnimationFrame(() => {
            messageDiv.classList.add('v2-error-animate-in');
        });
    }
};
