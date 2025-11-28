// Settings Module - Theme, Language, Modal Management
(function () {
    // Defer all DOM queries until document ready to ensure elements exist
    function openSettings(modal) { if (!modal) return; modal.classList.add('active'); modal.style.display = 'flex'; setTimeout(() => modal.style.opacity = '1', 10); }
    function closeSettings(modal) { if (!modal) return; modal.style.opacity = '0'; setTimeout(() => { modal.classList.remove('active'); modal.style.display = 'none'; }, 200); }

    document.addEventListener('DOMContentLoaded', () => {
        const modal = document.getElementById('settingsModal');
        const settingsBtn = document.getElementById('settingsBtn');
        const closeBtn = document.getElementById('closeSettingsBtn');
        const themeBtn = document.getElementById('themeDropdownBtn');
        const themeMenu = document.getElementById('themeDropdownMenu');
        const selectedTheme = document.getElementById('selectedTheme');
        const langBtn = document.getElementById('languageDropdownBtn');
        const langMenu = document.getElementById('languageDropdownMenu');
        const selectedLang = document.getElementById('selectedLanguage');

        // Safe defaults for menus
        if (themeMenu) themeMenu.style.display = themeMenu.style.display || 'none';
        if (langMenu) langMenu.style.display = langMenu.style.display || 'none';

        function applyAppearanceLocal(theme, persist = true) {
            if (theme === 'light') {
                document.body.classList.add('light-mode');
            } else if (theme === 'dark') {
                document.body.classList.remove('light-mode');
            }
            if (persist) localStorage.setItem('atlas-theme', theme);
            if (selectedTheme) {
                const cap = theme.charAt(0).toUpperCase() + theme.slice(1);
                selectedTheme.textContent = cap;
                // Update dropdown item active state (CSS will render checkmark)
                if (themeMenu) {
                    themeMenu.querySelectorAll('.dropdown-item').forEach(it => {
                        const t = it.getAttribute('data-theme');
                        if (t === theme) it.classList.add('active'); else it.classList.remove('active');
                    });
                }
            }
        }

        function applyLanguageLocal(lang, persist = true) {
            const labels = { 'en': 'English', 'es': 'Español', 'fr': 'Français', 'de': 'Deutsch', 'zh': '中文' };
            if (persist) localStorage.setItem('atlas-lang', lang);
            if (selectedLang) {
                selectedLang.textContent = labels[lang] || lang.toUpperCase();
            }
            console.log(`Language set to: ${lang}`);
        }

        // Initialize values from storage
        const savedTheme = localStorage.getItem('atlas-theme') || 'dark';
        applyAppearanceLocal(savedTheme, false);
        applyAppearanceLocal(savedTheme, true);
        const savedLang = localStorage.getItem('atlas-lang') || 'en';
        applyLanguageLocal(savedLang, false);
        applyLanguageLocal(savedLang, true);

        // Toggle handlers (prevent closing when interacting inside menus)
        themeBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            const currentDisplay = themeMenu ? themeMenu.style.display : 'none';
            if (themeMenu) themeMenu.style.display = currentDisplay === 'block' ? 'none' : 'block';
            if (langMenu) langMenu.style.display = 'none';
        });

        langBtn?.addEventListener('click', (e) => {
            e.stopPropagation();
            const currentDisplay = langMenu ? langMenu.style.display : 'none';
            if (langMenu) langMenu.style.display = currentDisplay === 'block' ? 'none' : 'block';
            if (themeMenu) themeMenu.style.display = 'none';
        });

        // Prevent clicks inside menus from closing them
        themeMenu?.addEventListener('click', (e) => { e.stopPropagation(); });
        langMenu?.addEventListener('click', (e) => { e.stopPropagation(); });

        // Dropdown item handlers
        themeMenu?.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', () => {
                const theme = item.getAttribute('data-theme');
                if (theme) { applyAppearanceLocal(theme, true); if (themeMenu) themeMenu.style.display = 'none'; }
            });
            item.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); item.click(); } });
        });

        langMenu?.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', () => {
                const lang = item.getAttribute('data-language');
                if (lang) { applyLanguageLocal(lang, true); if (langMenu) langMenu.style.display = 'none'; }
            });
            item.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); item.click(); } });
        });

        // Close menus on outside click
        document.addEventListener('click', () => {
            if (themeMenu) themeMenu.style.display = 'none';
            if (langMenu) langMenu.style.display = 'none';
        });

        // Modal open/close wiring
        settingsBtn?.addEventListener('click', (e) => { e.preventDefault(); openSettings(modal); });
        closeBtn?.addEventListener('click', (e) => { e.preventDefault(); closeSettings(modal); });
        // Clicking outside modal content closes it
        modal?.addEventListener('click', (e) => { if (e.target === modal) closeSettings(modal); });

        // Keyboard escape closes modal and menus
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (themeMenu) themeMenu.style.display = 'none';
                if (langMenu) langMenu.style.display = 'none';
                if (modal && modal.classList.contains('active')) closeSettings(modal);
            }
        });

        // Expose helpers
        if (typeof window.openSettings !== 'function') window.openSettings = () => openSettings(modal);
        if (typeof window.closeSettings !== 'function') window.closeSettings = () => closeSettings(modal);
    });

    // New Chat modal handlers
    document.addEventListener('DOMContentLoaded', () => {
        const newModal = document.getElementById('newChatModal');
        const newInput = document.getElementById('newChatTitle');
        const cancelBtn = document.getElementById('cancelNewChatBtn');
        const confirmBtn = document.getElementById('confirmNewChatBtn');

        function openNewChatModal(prefill = '') {
            if (!newModal) return;
            newModal.classList.add('active');
            newModal.style.display = 'flex';
            setTimeout(() => { newModal.style.opacity = '1'; if (newInput) { newInput.value = prefill; newInput.focus(); } }, 10);
        }

        function closeNewChatModal() {
            if (!newModal) return;
            newModal.style.opacity = '0';
            setTimeout(() => { newModal.classList.remove('active'); newModal.style.display = 'none'; if (newInput) newInput.value = ''; }, 200);
        }

        cancelBtn?.addEventListener('click', (e) => { e.preventDefault(); closeNewChatModal(); });

        confirmBtn?.addEventListener('click', async (e) => {
            e.preventDefault();
            const title = newInput?.value?.trim() || 'New Chat';
            closeNewChatModal();
            try {
                if (typeof ChatStore !== 'undefined') {
                    const chat = await ChatStore.createChat(title);
                    if (chat && chat.id) await ChatStore.openChat(chat.id);
                }
            } catch (err) { console.warn('Failed to create chat', err); }
        });

        newInput?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); confirmBtn?.click(); }
            if (e.key === 'Escape') { e.preventDefault(); closeNewChatModal(); }
        });

        // Close modal when clicking outside content
        newModal?.addEventListener('click', (e) => {
            if (e.target === newModal) closeNewChatModal();
        });

        // Expose opener
        if (typeof window.openNewChatModal !== 'function') window.openNewChatModal = openNewChatModal;
        if (typeof window.closeNewChatModal !== 'function') window.closeNewChatModal = closeNewChatModal;
    });

})();
