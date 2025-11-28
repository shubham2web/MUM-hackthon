// Sidebar Module
const Sidebar = {
    init() {
        const toggleBtn = document.getElementById('toggleBtn');
        const sidebar = document.getElementById('sidebar');

        toggleBtn?.addEventListener('click', () => {
            sidebar?.classList.toggle('collapsed');
        });

        // Wire History button
        const historyBtn = document.getElementById('historyBtn');
        if (historyBtn) {
            historyBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                const panel = document.getElementById('historyPanel');
                if (panel && panel.classList.contains('active')) {
                    panel.classList.remove('active');
                    return;
                }
                if (typeof ChatStore !== 'undefined' && typeof ChatStore.showHistoryPanel === 'function') {
                    await ChatStore.showHistoryPanel();
                }
            });
        }

        // Close history panel on close button
        const historyClose = document.getElementById('historyCloseBtn');
        if (historyClose) {
            historyClose.addEventListener('click', () => {
                const panel = document.getElementById('historyPanel');
                if (panel) panel.classList.remove('active');
            });
        }

        // Wire Clear History button
        const clearHistoryBtn = document.getElementById('clearHistoryBtn');
        if (clearHistoryBtn) {
            clearHistoryBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                if (confirm('Are you sure you want to clear all history? This cannot be undone.')) {
                    if (typeof ChatStore !== 'undefined' && typeof ChatStore.clearAllChats === 'function') {
                        await ChatStore.clearAllChats();
                        await ChatStore.showHistoryPanel();
                    }
                }
            });
        }

        // Close history panel when clicking outside
        document.addEventListener('click', (e) => {
            const panel = document.getElementById('historyPanel');
            if (!panel || !panel.classList.contains('active')) return;
            if (panel.contains(e.target)) return;
            if (historyBtn && historyBtn.contains(e.target)) return;
            panel.classList.remove('active');
        });
    }
};
