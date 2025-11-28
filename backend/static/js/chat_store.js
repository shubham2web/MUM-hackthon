// ChatStore: minimal frontend integration with /api/chats
const ChatStore = {
    baseURL: 'http://127.0.0.1:8000',
    currentChatId: null,
    currentChatIdByMode: JSON.parse(localStorage.getItem('chatIdsByMode') || '{}'),

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
            li.innerHTML = `<div class="h-title">${this.escapeHtml(c.title || 'Untitled')}</div><div class="h-meta">${this.formatTimestamp(c.created_at)}</div>`;
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
            const date = new Date(ts);
            const now = new Date();
            const diff = now - date;
            const mins = Math.floor(diff / 60000);
            const hours = Math.floor(diff / 3600000);
            const days = Math.floor(diff / 86400000);
            if (mins < 1) return 'Just now';
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
                    const messageText = msg.content || msg.text || '';
                    if (msg.role === 'user' && typeof Messages !== 'undefined') {
                        if (isHtml) {
                            Messages.addUserMessageWithHTML(messageText);
                        } else {
                            Messages.addUserMessage(messageText);
                        }
                    } else if (msg.role === 'assistant' && typeof Messages !== 'undefined') {
                        if (isHtml) {
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
        panel.classList.add('active');
    },

    escapeHtml(text) { const div = document.createElement('div'); div.textContent = text || ''; return div.innerHTML; }
};
