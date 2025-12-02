// Messages Module
const Messages = {
    container: null,
    thinkingInterval: null,  // Track dynamic thinking animation
    selectionMenu: null,     // Text selection context menu

    init(containerSelector) {
        this.container = document.querySelector(containerSelector);
        this.initSelectionMenu();
    },

    // Initialize the text selection context menu
    initSelectionMenu() {
        // Create the selection menu element
        this.selectionMenu = document.createElement('div');
        this.selectionMenu.className = 'text-selection-menu';
        this.selectionMenu.innerHTML = `
            <button class="selection-menu-item" data-action="summarize">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="21" y1="10" x2="3" y2="10"></line>
                    <line x1="21" y1="6" x2="3" y2="6"></line>
                    <line x1="21" y1="14" x2="3" y2="14"></line>
                    <line x1="21" y1="18" x2="3" y2="18"></line>
                </svg>
                Summarize
            </button>
            <button class="selection-menu-item" data-action="explain">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"></path>
                    <line x1="12" y1="17" x2="12.01" y2="17"></line>
                </svg>
                Explain this
            </button>
        `;
        this.selectionMenu.style.display = 'none';
        document.body.appendChild(this.selectionMenu);

        // Add event listeners for menu items
        this.selectionMenu.querySelectorAll('.selection-menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const action = item.dataset.action;
                const selectedText = this.currentSelectedText;
                this.hideSelectionMenu();
                if (selectedText && action) {
                    this.handleSelectionAction(action, selectedText);
                }
            });
        });

        // Listen for text selection on AI messages
        document.addEventListener('mouseup', (e) => this.handleTextSelection(e));
        document.addEventListener('mousedown', (e) => {
            // Hide menu if clicking outside
            if (!this.selectionMenu.contains(e.target)) {
                this.hideSelectionMenu();
            }
        });

        // Hide on scroll
        document.addEventListener('scroll', () => this.hideSelectionMenu(), true);
    },

    currentSelectedText: '',

    handleTextSelection(e) {
        const selection = window.getSelection();
        const selectedText = selection.toString().trim();

        // Check if selection is within an AI message
        if (selectedText.length > 0) {
            const range = selection.getRangeAt(0);
            const container = range.commonAncestorContainer;
            const aiMessage = container.nodeType === 3 
                ? container.parentElement.closest('.ai-message')
                : container.closest?.('.ai-message');

            if (aiMessage) {
                this.currentSelectedText = selectedText;
                this.showSelectionMenu(e, range);
                return;
            }
        }
        
        // Only hide if not clicking on the menu itself
        if (!this.selectionMenu.contains(e.target)) {
            this.hideSelectionMenu();
        }
    },

    showSelectionMenu(e, range) {
        const rect = range.getBoundingClientRect();
        const menuWidth = 180;
        const menuHeight = 200;
        
        // Position the menu above or below the selection
        let top = rect.bottom + window.scrollY + 8;
        let left = rect.left + window.scrollX + (rect.width / 2) - (menuWidth / 2);
        
        // Ensure menu stays within viewport
        if (left < 10) left = 10;
        if (left + menuWidth > window.innerWidth - 10) {
            left = window.innerWidth - menuWidth - 10;
        }
        
        // If menu would go below viewport, show above selection
        if (top + menuHeight > window.innerHeight + window.scrollY) {
            top = rect.top + window.scrollY - menuHeight - 8;
        }

        this.selectionMenu.style.left = `${left}px`;
        this.selectionMenu.style.top = `${top}px`;
        this.selectionMenu.style.display = 'block';
        
        // Animate in
        requestAnimationFrame(() => {
            this.selectionMenu.classList.add('visible');
        });
    },

    hideSelectionMenu() {
        this.selectionMenu.classList.remove('visible');
        setTimeout(() => {
            this.selectionMenu.style.display = 'none';
        }, 150);
    },

    async handleSelectionAction(action, text) {
        // Clear selection
        window.getSelection().removeAllRanges();

        // Show the selected text as user message
        const actionLabel = action === 'summarize' ? '📝 Summarize' : '💡 Explain';
        this.addUserMessage(`${actionLabel}: "${text.length > 100 ? text.substring(0, 100) + '...' : text}"`);

        // Show loading indicator
        this.showLoading();

        // Show loading state on send button if Chat module is available
        if (typeof Chat !== 'undefined' && Chat.showLoadingState) {
            Chat.showLoadingState();
        }

        try {
            // Call the text_action endpoint with fallback strategy
            const response = await fetch('/text_action', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': typeof API_KEY !== 'undefined' ? API_KEY : ''
                },
                body: JSON.stringify({
                    action: action,
                    text: text
                })
            });

            this.hideLoading();

            const data = await response.json();

            if (data.success && data.result) {
                // Show which provider was used (for debugging/transparency)
                const providerBadge = data.provider ? ` <span style="opacity: 0.5; font-size: 0.8em;">(via ${data.provider})</span>` : '';
                this.addAIMessage(data.result + providerBadge);
            } else {
                this.addAIMessage(`❌ Error: ${data.error || 'Failed to process text'}`);
            }
        } catch (error) {
            this.hideLoading();
            console.error('Text action error:', error);
            this.addAIMessage(`❌ Error: ${error.message || 'Failed to connect to server'}`);
        } finally {
            // Hide loading state on send button
            if (typeof Chat !== 'undefined' && Chat.hideLoadingState) {
                Chat.hideLoadingState();
            }
        }
    },

    addUserMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-avatar">You</div>
                <div class="message-text">${this.escapeHtml(text)}</div>
            </div>
            <div class="message-time">${this.getTimeString()}</div>
        `;
        this.container.appendChild(messageDiv);
        this.scrollToBottom();
    },

    addUserMessageWithHTML(htmlContent) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message user-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-avatar">You</div>
                <div class="message-text">${htmlContent}</div>
            </div>
            <div class="message-time">${this.getTimeString()}</div>
        `;
        this.container.appendChild(messageDiv);
        this.scrollToBottom();
    },

    addAIMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-avatar">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.5 3-9s-1.343-9-3-9m-9 9a9 9 0 019 9m-9-9a9 9 0 009-9m-9 9h12"/>
                    </svg>
                </div>
                <div class="message-text">${this.formatMarkdown(text)}</div>
            </div>
            <div class="message-time">${this.getTimeString()}</div>
        `;
        this.container.appendChild(messageDiv);
        this.scrollToBottom();
    },

    addAIMessageHTML(htmlContent) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        messageDiv.innerHTML = `
            <div class="message-content">
                <div class="message-avatar">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.5 3-9s-1.343-9-3-9m-9 9a9 9 0 019 9m-9-9a9 9 0 009-9m-9 9h12"/>
                    </svg>
                </div>
                <div class="message-text">${htmlContent}</div>
            </div>
            <div class="message-time">${this.getTimeString()}</div>
        `;
        this.container.appendChild(messageDiv);
        this.scrollToBottom();
    },

    showLoading() {
        // Dynamic Thinking states that cycle every 2.5 seconds
        const thinkingStates = [
            "🧠 Searching Internal Memory...",
            "🌐 Accessing Web Tools...",
            "⚡ Fetching External Sources...",
            "📑 Reading & Summarizing Content...",
            "🤖 Generating Analysis..."
        ];
        
        let currentStateIndex = 0;
        
        const loadingDiv = document.createElement('div');
        loadingDiv.className = 'message ai-message loading-message';
        loadingDiv.id = 'loading-indicator';
        loadingDiv.style.opacity = '1';
        loadingDiv.style.transform = 'translateY(0)';
        loadingDiv.innerHTML = `
            <div class="message-content">
                <div class="message-avatar">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.5 3-9s-1.343-9-3-9m-9 9a9 9 0 019 9m-9-9a9 9 0 009-9m-9 9h12"/>
                    </svg>
                </div>
                <div class="message-text">
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                    <div class="thinking-status" style="margin-top: 8px; font-size: 0.9em; color: rgba(255, 255, 255, 0.7); transition: opacity 0.3s ease;">
                        ${thinkingStates[0]}
                    </div>
                </div>
            </div>
        `;
        this.container.appendChild(loadingDiv);
        this.scrollToBottom();
        
        // Start cycling through thinking states
        const statusElement = loadingDiv.querySelector('.thinking-status');
        this.thinkingInterval = setInterval(() => {
            // Fade out
            statusElement.style.opacity = '0';
            
            setTimeout(() => {
                // Change text and fade in
                currentStateIndex = (currentStateIndex + 1) % thinkingStates.length;
                statusElement.textContent = thinkingStates[currentStateIndex];
                statusElement.style.opacity = '1';
            }, 300); // Wait for fade out to complete
            
        }, 2500); // Change every 2.5 seconds
    },

    hideLoading() {
        // Clear the thinking animation interval
        if (this.thinkingInterval) {
            clearInterval(this.thinkingInterval);
            this.thinkingInterval = null;
        }
        
        const loading = document.getElementById('loading-indicator');
        if (loading) {
            loading.remove();
        }
        // Also remove any other loading messages that might exist
        const allLoading = document.querySelectorAll('.loading-message');
        allLoading.forEach(el => el.remove());
    },

    scrollToBottom() {
        this.container.scrollTop = this.container.scrollHeight;
    },

    formatMarkdown(text) {
        return text
            // Convert URLs to clickable links (must be done before other markdown processing)
            // Matches http://, https://, and www. URLs
            .replace(/(https?:\/\/[^\s<]+[^<.,:;"')\]\s])/g, '<a href="$1" target="_blank" rel="noopener noreferrer" class="message-link">$1</a>')
            .replace(/(?<!https?:\/\/)(?<!["\'>])(www\.[^\s<]+[^<.,:;"')\]\s])/g, '<a href="http://$1" target="_blank" rel="noopener noreferrer" class="message-link">$1</a>')
            // Bold text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Italic text
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Line breaks
            .replace(/\n/g, '<br>');
    },

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    getTimeString() {
        return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    },

    // === GOD MODE: RENDER ARTIFACTS ===
    renderGodModeArtifacts(messageDiv, meta) {
        if (!meta) return;

        // Get the message-text container to append God Mode elements
        const messageText = messageDiv.querySelector('.message-text');
        if (!messageText) return;

        // --- A. Render Citation Card ---
        if (meta.primary_source || meta.rag_status) {
            const card = document.createElement('div');
            card.className = 'god-mode-card';
            
            // Logic to determine badge style
            let badgeClass = 'badge-live';
            let badgeText = 'LIVE FETCH';
            let icon = '🌐';

            if (meta.rag_status === 'CACHE_HIT') {
                badgeClass = 'badge-cache';
                badgeText = `⚡ CACHE (${meta.latency}s)`;
                icon = '⚡';
            } else if (meta.rag_status === 'VECTOR_RECALL' || meta.memory_active) {
                badgeClass = 'badge-brain';
                badgeText = '🧠 MEMORY';
                icon = '🧠';
            } else if (meta.rag_status === 'INTERNAL_KNOWLEDGE') {
                badgeClass = 'badge-brain';
                badgeText = '🧠 INTERNAL';
                icon = '🧠';
            }

            let sourceHtml = '';
            if (meta.primary_source) {
                sourceHtml = `<span style="opacity:0.7">via</span>
                <a href="#" class="god-mode-source">${meta.primary_source}</a>`;
            }

            card.innerHTML = `
                <span class="god-mode-badge ${badgeClass}">${icon} ${badgeText}</span>
                ${sourceHtml}
            `;
            
            messageText.appendChild(card);
        }

        // --- B. Trigger Memory Toast ---
        // Only show toast for NEW knowledge being stored (LIVE_FETCH + memory active)
        // Don't show for CACHE hits or pure MEMORY recalls
        if (meta.memory_active && meta.rag_status === 'LIVE_FETCH') {
            this.triggerMemoryToast();
        }
    },

    // === GOD MODE: MEMORY TOAST ANIMATION ===
    triggerMemoryToast() {
        // Check if container exists
        let container = document.getElementById('memory-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'memory-toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = 'memory-toast';
        toast.innerHTML = `<span>🧠</span> KNOWLEDGE PERMANENTLY STORED`;
        
        container.appendChild(toast);

        // Animate In
        requestAnimationFrame(() => toast.classList.add('active'));

        // Remove after 3s
        setTimeout(() => {
            toast.classList.remove('active');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};
