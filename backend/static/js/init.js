// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Atlas Chat...');
    
    // ===== CRITICAL: Check for homepage query BEFORE anything else =====
    // This must happen before ChatStore loads its values from localStorage
    const forceNewChat = sessionStorage.getItem('forceNewChat');
    const initialPrompt = sessionStorage.getItem('initialPrompt');
    
    // If either flag is set OR there's an initial prompt, we need a fresh chat
    const needsNewChat = (forceNewChat === 'true') || (initialPrompt && initialPrompt.length > 0);
    
    if (needsNewChat) {
        console.log('🆕 Homepage query detected in init.js - clearing ALL chat state');
        console.log('   forceNewChat:', forceNewChat);
        console.log('   initialPrompt:', initialPrompt ? initialPrompt.substring(0, 50) + '...' : 'none');
        
        // Clear chat ID mappings to ensure a fresh chat is created
        localStorage.removeItem('chatIdsByMode');
        
        // Also update ChatStore if it already loaded (it reads from localStorage at declaration)
        if (typeof ChatStore !== 'undefined') {
            ChatStore.currentChatId = null;
            ChatStore.currentChatIdByMode = {};
            console.log('✅ ChatStore state cleared');
        }
    }
    
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
                
                // Show animated notification for V2 mode
                showV2Notification();
            } else {
                v2Slider.style.transform = 'translateX(0)';
                v2Slider.parentElement.style.backgroundColor = 'rgba(255,255,255,0.2)';
                console.log('❌ v2.0 Enhanced Analysis: DISABLED');
                
                // Hide notification if visible
                hideV2Notification();
            }
        });
    }
    
    console.log('✅ Atlas Chat initialized successfully');
});

/**
 * Show animated V2 notification banner
 */
function showV2Notification() {
    // Remove existing notification if any
    hideV2Notification();
    
    const notification = document.createElement('div');
    notification.id = 'v2-notification';
    notification.className = 'v2-notification';
    notification.innerHTML = `
        <div class="v2-notification-content">
            <div class="v2-notification-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
                </svg>
            </div>
            <div class="v2-notification-text">
                <div class="v2-notification-title">🔗 V2.5 Enhanced Analysis Activated</div>
                <div class="v2-notification-message">This mode analyzes <strong>URLs and links only</strong>. Paste a news article or webpage link to get comprehensive credibility analysis with visual insights.</div>
            </div>
            <button class="v2-notification-close" onclick="hideV2Notification()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M18 6L6 18M6 6l12 12"/>
                </svg>
            </button>
        </div>
        <div class="v2-notification-progress"></div>
    `;
    
    document.body.appendChild(notification);
    
    // Trigger animation
    requestAnimationFrame(() => {
        notification.classList.add('show');
    });
    
    // Auto-hide after 8 seconds
    setTimeout(() => {
        hideV2Notification();
    }, 8000);
}

/**
 * Hide V2 notification with animation
 */
function hideV2Notification() {
    const notification = document.getElementById('v2-notification');
    if (notification) {
        notification.classList.remove('show');
        notification.classList.add('hide');
        setTimeout(() => {
            notification.remove();
        }, 400);
    }
}

// Make functions globally available
window.showV2Notification = showV2Notification;
window.hideV2Notification = hideV2Notification;
