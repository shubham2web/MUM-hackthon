// Messages Module
const Messages = {
    container: null,

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
                </div>
            </div>
        `;
        this.container.appendChild(loadingDiv);
        this.scrollToBottom();
    },

    hideLoading() {
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
    }
};
