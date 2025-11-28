// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Atlas Chat...');
    
    // Central theme applier so it's available before components initialize
    window.applyTheme = function(theme) {
        if (theme === 'light') {
            document.body.classList.add('light-mode');
        } else if (theme === 'dark') {
            document.body.classList.remove('light-mode');
        }
        localStorage.setItem('atlas-theme', theme);
        
        // Update settings dropdown if present
        const selectedTheme = document.getElementById('selectedTheme');
        if (selectedTheme) {
            const cap = theme.charAt(0).toUpperCase() + theme.slice(1);
            selectedTheme.textContent = cap;
        }
        
        // Update theme buttons
        document.querySelectorAll('.theme-btn').forEach(btn => {
            const btnTheme = btn.getAttribute('data-theme');
            if (btnTheme === theme) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
        
        console.log(`Theme applied: ${theme}`);
    };

    // Apply saved theme before initializing components
    const savedTheme = localStorage.getItem('atlas-theme') || 'dark';
    applyTheme(savedTheme);

    // Initialize chat persistence UI (do not auto-list chats; History button opens them)
    try { ChatStore.init(); } catch (e) { console.warn('ChatStore init error', e); }

    // HISTORY button: show recent chats when clicked
    try {
        const historyBtn = document.getElementById('historyBtn');
        if (historyBtn) {
            historyBtn.addEventListener('click', async (e) => {
                e.preventDefault();
                await ChatStore.showHistoryPanel();
            });
        }
    } catch (err) { console.warn('Failed to wire History button', err); }

    Chat.init();
    Sidebar.init();
    Attachments.init(); // Initialize attachment functionality
    
    // Initialize v2.0 toggle
    const v2Toggle = document.getElementById('v2Toggle');
    const v2Slider = document.getElementById('v2ToggleSlider');
    
    if (v2Toggle && v2Slider) {
        v2Toggle.addEventListener('change', function() {
            if (this.checked) {
                v2Slider.style.transform = 'translateX(26px)';
                v2Slider.parentElement.style.backgroundColor = '#3b82f6';
                console.log('✅ v2.0 Enhanced Analysis: ENABLED');
            } else {
                v2Slider.style.transform = 'translateX(0)';
                v2Slider.parentElement.style.backgroundColor = 'rgba(255,255,255,0.2)';
                console.log('❌ v2.0 Enhanced Analysis: DISABLED');
            }
        });
    }
    
    console.log('✅ Atlas Chat initialized successfully');
});
