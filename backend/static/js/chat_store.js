// ChatStore: minimal frontend integration with /api/chats
const ChatStore = {
    baseURL: 'http://127.0.0.1:8000',
    currentChatId: null,
    // Load from localStorage - but check for homepage query first
    currentChatIdByMode: (function() {
        // If forceNewChat flag OR initialPrompt is set, return empty object
        var forceNewChat = sessionStorage.getItem('forceNewChat');
        var initialPrompt = sessionStorage.getItem('initialPrompt');
        var needsNewChat = (forceNewChat === 'true') || (initialPrompt && initialPrompt.length > 0);
        
        if (needsNewChat) {
            console.log('🆕 ChatStore: Homepage query detected, starting with empty chat mappings');
            return {};
        }
        return JSON.parse(localStorage.getItem('chatIdsByMode') || '{}');
    })(),

    init() {
        // Wire "New Chat" button at bottom of sidebar
        const newChatBtn = document.getElementById('newChatBtn');
        if (newChatBtn) {
            newChatBtn.addEventListener('click', async () => {
                if (typeof window.openNewChatModal === 'function') {
                    window.openNewChatModal('');
                }
            });
        }
    },

    async renderList(chats) {
        const list = document.getElementById('historyList');
        if (!list) return;
        list.innerHTML = '';
        if (!chats || chats.length === 0) {
            list.innerHTML = '<li style="color:rgba(255,255,255,0.5); text-align:center; padding:20px;">No chats yet</li>';
            return;
        }
        chats.forEach(c => {
            const li = document.createElement('li');
            // store original timestamp on element for live-refresh
            const ts = c.created_at || c.createdAt || Date.now();
            li.innerHTML = `<div class="h-title">${this.escapeHtml(c.title || 'Untitled')}</div><div class="h-meta">${this.formatTimestamp(ts)}</div>`;
            li.setAttribute('data-ts', ts);
            li.style.position = 'relative';
            li.addEventListener('click', async () => {
                await this.openChat(c.id);
                const panel = document.getElementById('historyPanel');
                if (panel) panel.classList.remove('active');
            });
            list.appendChild(li);
        });
    },

    formatTimestamp(ts) {
        try {
            // Normalise timestamp formats:
            // - If timestamp looks like ISO without timezone (e.g. 2025-11-22T21:52:20.317146),
            //   JavaScript may interpret it as local; server emits naive UTC isoformat(),
            //   so treat naive ISO strings as UTC by appending 'Z'.
            let raw = ts;
            if (typeof raw === 'number') {
                // assume milliseconds
                raw = Number(raw);
            }
            let date;
            if (typeof raw === 'string') {
                // ISO-like without timezone: YYYY-MM-DDTHH:MM:SS
                const isoLike = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?$/;
                if (isoLike.test(raw)) {
                    // If it doesn't end with Z or timezone offset, append Z to treat as UTC
                    if (!/[Z+\-]\d{2}:?\d{2}$/.test(raw) && !raw.endsWith('Z')) {
                        raw = raw + 'Z';
                    }
                }
                date = new Date(raw);
            } else {
                date = new Date(raw);
            }

            if (isNaN(date.getTime())) return String(ts);

            const now = new Date();
            const diffMs = now - date;
            const secs = Math.floor(diffMs / 1000);
            const mins = Math.floor(diffMs / 60000);
            const hours = Math.floor(diffMs / 3600000);
            const days = Math.floor(diffMs / 86400000);

            if (secs < 5) return 'Just now';
            if (secs < 60) return `${secs}s ago`;
            if (mins < 60) return `${mins}m ago`;
            if (hours < 24) return `${hours}h ago`;
            if (days === 1) return 'Yesterday';
            if (days < 7) return `${days}d ago`;
            return date.toLocaleDateString();
        } catch (e) { return String(ts); }
    },

    async listChats() {
        try {
            const res = await fetch(`${this.baseURL}/api/chats`, { method: 'GET' });
            if (!res.ok) throw new Error(`list chats error: ${res.status}`);
            const data = await res.json();
            return data.chats || [];
        } catch (e) {
            console.warn('listChats error', e);
            return [];
        }
    },

    async createChat(title = 'New Chat') {
        try {
            const res = await fetch(`${this.baseURL}/api/chats`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title })
            });
            if (!res.ok) throw new Error(`createChat error: ${res.status}`);
            const data = await res.json();
            console.log('✅ Chat created:', data);
            if (typeof Chat !== 'undefined' && Chat.currentMode) {
                this.currentChatIdByMode[Chat.currentMode] = data.chat.id;
                localStorage.setItem('chatIdsByMode', JSON.stringify(this.currentChatIdByMode));
            }
            return data.chat;
        } catch (e) { console.warn('createChat error', e); throw e; }
    },

    async openChat(id) {
        try {
            const res = await fetch(`${this.baseURL}/api/chats/${id}`, { method: 'GET' });
            if (!res.ok) throw new Error(`openChat error: ${res.status}`);
            const data = await res.json();
            console.log('📂 Chat opened:', data.chat);
            this.currentChatId = id;
            if (typeof Chat !== 'undefined' && Chat.currentMode) {
                this.currentChatIdByMode[Chat.currentMode] = id;
                localStorage.setItem('chatIdsByMode', JSON.stringify(this.currentChatIdByMode));
            }
            const messages = document.getElementById('chatMessages');
            if (messages) messages.innerHTML = '';
            if (data.chat.messages && data.chat.messages.length > 0) {
                data.chat.messages.forEach(msg => {
                    const isHtml = msg.metadata && msg.metadata.is_html;
                    const isV2Dashboard = msg.metadata && msg.metadata.is_v2_dashboard;
                    const messageText = msg.content || msg.text || '';
                    
                    if (msg.role === 'user' && typeof Messages !== 'undefined') {
                        if (isHtml) {
                            Messages.addUserMessageWithHTML(messageText);
                        } else {
                            Messages.addUserMessage(messageText);
                        }
                    } else if (msg.role === 'assistant' && typeof Messages !== 'undefined') {
                        // Check if this is a V2 dashboard response that needs re-rendering
                        if (isV2Dashboard || this.isV2DashboardData(messageText)) {
                            this.renderV2Dashboard(messageText);
                        } else if (isHtml) {
                            Messages.addAIMessageHTML(messageText);
                        } else {
                            Messages.addAIMessage(messageText);
                        }
                    }
                });
            } else {
                if (typeof Chat !== 'undefined' && typeof Chat.addWelcomeMessage === 'function') {
                    Chat.addWelcomeMessage();
                }
            }
        } catch (e) { console.warn('openChat error', e); }
    },

    /**
     * Check if message content is V2 dashboard JSON data
     */
    isV2DashboardData(text) {
        if (!text || typeof text !== 'string') return false;
        try {
            // Check if it starts with JSON object marker
            if (!text.trim().startsWith('{')) return false;
            const parsed = JSON.parse(text);
            return parsed && parsed.__v2_dashboard__ === true;
        } catch (e) {
            return false;
        }
    },

    /**
     * Render V2 dashboard from stored JSON data
     */
    renderV2Dashboard(text) {
        try {
            let v2Data;
            if (typeof text === 'string') {
                const parsed = JSON.parse(text);
                v2Data = parsed.data || parsed;
            } else {
                v2Data = text;
            }
            
            // Use ATLASv25 to render the dashboard
            if (typeof window.ATLASv25 !== 'undefined' && typeof window.ATLASv25.renderDashboard === 'function') {
                const dashboardHtml = window.ATLASv25.renderDashboard(v2Data);
                if (typeof Chat !== 'undefined' && typeof Chat.addV2Card === 'function') {
                    Chat.addV2Card(dashboardHtml);
                } else {
                    // Fallback: add directly to messages
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message ai-message v2-message';
                    messageDiv.style.background = 'transparent';
                    messageDiv.style.padding = '0';
                    messageDiv.style.margin = '8px 0';
                    messageDiv.innerHTML = dashboardHtml;
                    const container = document.getElementById('chatMessages');
                    if (container) container.appendChild(messageDiv);
                }
            } else if (typeof V2UI !== 'undefined' && typeof V2UI.createV2ResponseCard === 'function') {
                // Fallback to V2UI
                const v2Card = V2UI.createV2ResponseCard(v2Data);
                if (typeof Chat !== 'undefined' && typeof Chat.addV2Card === 'function') {
                    Chat.addV2Card(v2Card);
                }
            } else {
                // Last resort: show as formatted text
                console.warn('V2 dashboard renderer not available, showing as text');
                if (typeof Messages !== 'undefined') {
                    Messages.addAIMessage(v2Data.synthesis || JSON.stringify(v2Data, null, 2));
                }
            }
        } catch (e) {
            console.warn('Failed to render V2 dashboard:', e);
            // Show raw text as fallback
            if (typeof Messages !== 'undefined') {
                Messages.addAIMessage(text);
            }
        }
    },

    async appendMessage(chatId, role, text, metadata = {}) {
        try {
            const res = await fetch(`${this.baseURL}/api/chats/${chatId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ role, text, metadata })
            });
            if (!res.ok) throw new Error(`appendMessage error: ${res.status}`);
            const data = await res.json();
            return data.message;
        } catch (e) { console.warn('appendMessage error', e); return null; }
    },

    async deleteChat(id) {
        try {
            const res = await fetch(`${this.baseURL}/api/chats/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error(`deleteChat error: ${res.status}`);
            console.log('🗑️ Chat deleted:', id);
            if (this.currentChatId === id) this.currentChatId = null;
            const mode = typeof Chat !== 'undefined' ? Chat.currentMode : null;
            if (mode && this.currentChatIdByMode[mode] === id) delete this.currentChatIdByMode[mode];
        } catch (e) { console.warn('deleteChat error', e); throw e; }
    },

    async clearAllChats() {
        try {
            const res = await fetch(`${this.baseURL}/api/chats/clear`, { method: 'POST' });
            if (!res.ok) throw new Error(`clearAllChats error: ${res.status}`);
            console.log('🗑️ All chats deleted');
            this.currentChatId = null;
            this.currentChatIdByMode = {};
            localStorage.removeItem('chatIdsByMode');
        } catch (e) { console.warn('clearAllChats error', e); throw e; }
    },

    async showHistoryPanel() {
        const panel = document.getElementById('historyPanel');
        if (!panel) return;
        const chats = await this.listChats();
        await this.renderList(chats);
        // clear any existing refresh interval
        if (this._historyRefreshInterval) {
            clearInterval(this._historyRefreshInterval);
            this._historyRefreshInterval = null;
        }

        // Refresh displayed timestamps every 10 seconds while history panel is open
        const refreshFn = () => {
            const list = document.getElementById('historyList');
            if (!list) return;
            const items = list.querySelectorAll('li[data-ts]');
            items.forEach(li => {
                const ts = li.getAttribute('data-ts');
                const meta = li.querySelector('.h-meta');
                if (meta) meta.textContent = this.formatTimestamp(ts);
            });
        };

        // run immediately and then every 10s
        refreshFn();
        this._historyRefreshInterval = setInterval(refreshFn, 10000);

        // Observe panel so we can clear interval when panel is closed (class 'active' removed)
        const observer = new MutationObserver((mutations) => {
            for (const m of mutations) {
                if (m.attributeName === 'class') {
                    if (!panel.classList.contains('active')) {
                        if (this._historyRefreshInterval) {
                            clearInterval(this._historyRefreshInterval);
                            this._historyRefreshInterval = null;
                        }
                        observer.disconnect();
                    }
                }
            }
        });
        observer.observe(panel, { attributes: true });

        panel.classList.add('active');
    },

    escapeHtml(text) { const div = document.createElement('div'); div.textContent = text || ''; return div.innerHTML; }
};
