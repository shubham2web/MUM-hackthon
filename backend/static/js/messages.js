// Messages Module
const Messages = {
    container: null,
    thinkingInterval: null,  // Track dynamic thinking animation

    init(containerSelector) {
        this.container = document.querySelector(containerSelector);
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
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
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
        if (meta.memory_active) {
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
