// Fake News Detective - Game Logic

class GameManager {
    constructor() {
        this.userId = this.getUserId();
        this.currentHeadlines = [];
        this.answerIndex = -1;
        this.selectedIndex = -1;
        this.gameStats = this.loadStats();
        this.dailyLimit = 10;
        this.roundHistory = [];
        this.currentRoundIndex = -1;
        this.hasAnswered = false;
        
        this.init();
    }

    getUserId() {
        let userId = localStorage.getItem('fakeNewsUserId');
        if (!userId) {
            userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('fakeNewsUserId', userId);
        }
        return userId;
    }

    init() {
        this.checkDailyReset();
        this.updateStatsDisplay();
        
        if (this.gameStats.gamesPlayedToday >= this.dailyLimit) {
            if (this.roundHistory.length > 0) {
                this.currentRoundIndex = this.roundHistory.length - 1;
                this.loadRoundFromHistory(this.currentRoundIndex);
                this.updateNavButtons();
            } else {
                this.showLimitReached();
            }
        } else {
            this.loadNewRound();
        }
    }

    loadStats() {
        const defaultStats = {
            gamesPlayedToday: 0,
            currentStreak: 0,
            bestStreak: 0,
            totalCorrect: 0,
            totalGames: 0,
            lastPlayedDate: new Date().toDateString()
        };
        
        const saved = localStorage.getItem(`fakeNewsGameStats_${this.userId}`);
        return saved ? JSON.parse(saved) : defaultStats;
    }

    saveStats() {
        localStorage.setItem(`fakeNewsGameStats_${this.userId}`, JSON.stringify(this.gameStats));
    }

    loadHistory() {
        const saved = localStorage.getItem(`fakeNewsHistory_${this.userId}_${new Date().toDateString()}`);
        return saved ? JSON.parse(saved) : [];
    }

    saveHistory() {
        localStorage.setItem(`fakeNewsHistory_${this.userId}_${new Date().toDateString()}`, JSON.stringify(this.roundHistory));
    }

    checkDailyReset() {
        const today = new Date().toDateString();
        if (this.gameStats.lastPlayedDate !== today) {
            this.gameStats.gamesPlayedToday = 0;
            this.gameStats.lastPlayedDate = today;
            this.saveStats();
            // Clear old history
            this.roundHistory = [];
            this.saveHistory();
        } else {
            this.roundHistory = this.loadHistory();
        }
    }

    updateStatsDisplay() {
        const gamesElement = document.getElementById('games-today');
        const streakElement = document.getElementById('current-streak');
        const bestElement = document.getElementById('best-streak');
        const accuracyElement = document.getElementById('accuracy');
        
        // Add animation class
        [gamesElement, streakElement, bestElement, accuracyElement].forEach(el => {
            el?.classList.add('updated');
            setTimeout(() => el?.classList.remove('updated'), 500);
        });
        
        gamesElement.textContent = 
            `${this.gameStats.gamesPlayedToday}/${this.dailyLimit}`;
        
        streakElement.textContent = 
            this.gameStats.currentStreak;
        
        bestElement.textContent = 
            this.gameStats.bestStreak;
        
        const accuracy = this.gameStats.totalGames > 0 
            ? Math.round((this.gameStats.totalCorrect / this.gameStats.totalGames) * 100)
            : 0;
        accuracyElement.textContent = `${accuracy}%`;
    }

    async loadNewRound() {
        const loadingState = document.getElementById('loading-state');
        const gameState = document.getElementById('game-state');
        
        loadingState.classList.remove('hidden');
        gameState.classList.add('hidden');
        
        try {
            const response = await fetch(`/api/game/headlines?userId=${this.userId}&seed=${Date.now()}`);
            if (!response.ok) throw new Error('Failed to fetch headlines');
            
            const data = await response.json();
            this.currentHeadlines = data.items;
            this.answerIndex = data.answerIndex;
            this.selectedIndex = -1;
            this.hasAnswered = false;
            
            this.renderHeadlines();
            this.updateNavButtons();
            
            loadingState.classList.add('hidden');
            gameState.classList.remove('hidden');
        } catch (error) {
            console.error('Error loading headlines:', error);
            this.showError('Failed to load headlines. Please try again.');
        }
    }

    loadRoundFromHistory(index) {
        if (index < 0 || index >= this.roundHistory.length) return;
        
        const round = this.roundHistory[index];
        this.currentHeadlines = round.headlines;
        this.answerIndex = round.answerIndex;
        this.selectedIndex = round.selectedIndex;
        this.hasAnswered = true;
        
        const loadingState = document.getElementById('loading-state');
        const gameState = document.getElementById('game-state');
        const limitState = document.getElementById('limit-state');
        
        loadingState.classList.add('hidden');
        limitState.classList.add('hidden');
        gameState.classList.remove('hidden');
        
        this.renderHeadlines();
        this.showResults(round.isCorrect, round.selectedIndex, true);
        this.updateNavButtons();
    }

    renderHeadlines() {
        const container = document.getElementById('headlines-grid');
        container.innerHTML = '';
        
        this.currentHeadlines.forEach((headline, index) => {
            const card = document.createElement('div');
            card.className = 'headline-card';
            card.dataset.index = index;
            
            card.innerHTML = `
                <div class="headline-number">${index + 1}</div>
                <div class="headline-title">${this.escapeHtml(headline.title)}</div>
                <div class="headline-source">${this.escapeHtml(headline.source)}</div>
            `;
            
            card.addEventListener('click', () => this.handleGuess(index));
            container.appendChild(card);
        });
    }

    handleGuess(index) {
        if (this.selectedIndex !== -1) return; // Already guessed
        
        this.selectedIndex = index;
        const isCorrect = index === this.answerIndex;
        this.hasAnswered = true;
        
        // Update stats
        this.gameStats.gamesPlayedToday++;
        this.gameStats.totalGames++;
        
        if (isCorrect) {
            this.gameStats.totalCorrect++;
            this.gameStats.currentStreak++;
            if (this.gameStats.currentStreak > this.gameStats.bestStreak) {
                this.gameStats.bestStreak = this.gameStats.currentStreak;
            }
        } else {
            this.gameStats.currentStreak = 0;
        }
        
        // Save round to history
        const roundData = {
            headlines: this.currentHeadlines,
            answerIndex: this.answerIndex,
            selectedIndex: this.selectedIndex,
            isCorrect: isCorrect,
            timestamp: Date.now()
        };
        this.roundHistory.push(roundData);
        this.currentRoundIndex = this.roundHistory.length - 1;
        this.saveHistory();
        
        this.saveStats();
        this.updateStatsDisplay();
        
        // Visual feedback
        this.showResults(isCorrect, index, false);
        this.updateNavButtons();
    }

    showResults(isCorrect, selectedIndex, isViewingHistory) {
        const cards = document.querySelectorAll('.headline-card');
        
        // Disable all cards
        cards.forEach(card => card.classList.add('disabled'));
        
        // Mark selected card
        cards[selectedIndex].classList.add(isCorrect ? 'correct' : 'incorrect');
        
        // Always show the correct answer
        if (!isCorrect) {
            cards[this.answerIndex].classList.add('correct');
        }
        
        // Add badges
        const selectedBadge = document.createElement('div');
        selectedBadge.className = `result-badge ${isCorrect ? 'correct' : 'incorrect'}`;
        if (isCorrect) {
            selectedBadge.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"/>
                </svg>
                Correct
            `;
        } else {
            selectedBadge.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <line x1="18" y1="6" x2="6" y2="18"/>
                    <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
                Wrong
            `;
        }
        cards[selectedIndex].appendChild(selectedBadge);
        
        if (!isCorrect) {
            const answerBadge = document.createElement('div');
            answerBadge.className = 'result-badge answer';
            answerBadge.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>
                </svg>
                Satire
            `;
            cards[this.answerIndex].appendChild(answerBadge);
        }
        
        // Show modal only if not viewing history
        if (!isViewingHistory) {
            this.showResultModal(isCorrect, selectedIndex);
        }
    }

    showResultModal(isCorrect, selectedIndex) {
        const modal = document.getElementById('result-modal');
        const icon = document.getElementById('result-icon');
        const title = document.getElementById('result-title');
        const message = document.getElementById('result-message');
        const details = document.getElementById('result-details');
        
        if (isCorrect) {
            icon.innerHTML = `
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="var(--game-success)" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
            `;
            title.textContent = 'Excellent Detective Work!';
            title.style.color = 'var(--game-success)';
            message.textContent = 'You correctly identified the satirical headline!';
            details.innerHTML = `
                <strong>Correct Answer:</strong><br>
                "${this.escapeHtml(this.currentHeadlines[this.answerIndex].title)}"<br><br>
                <strong>Source:</strong> ${this.escapeHtml(this.currentHeadlines[this.answerIndex].source)}
                (Satire Publication)
            `;
        } else {
            icon.innerHTML = `
                <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="var(--game-error)" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
            `;
            title.textContent = 'Not Quite Right';
            title.style.color = 'var(--game-error)';
            message.textContent = 'That was actually a real news headline!';
            details.innerHTML = `
                <strong>You Selected:</strong><br>
                "${this.escapeHtml(this.currentHeadlines[selectedIndex].title)}"<br>
                <em>(Real news from ${this.escapeHtml(this.currentHeadlines[selectedIndex].source)})</em><br><br>
                <strong>The Satire Was:</strong><br>
                "${this.escapeHtml(this.currentHeadlines[this.answerIndex].title)}"<br>
                <em>(From ${this.escapeHtml(this.currentHeadlines[this.answerIndex].source)})</em>
            `;
        }
        
        modal.classList.add('show');
    }

    closeResultModal() {
        const modal = document.getElementById('result-modal');
        modal.classList.remove('show');
    }

    updateNavButtons() {
        const prevBtn = document.getElementById('btn-prev');
        const nextBtn = document.getElementById('btn-next');
        const continueBtn = document.getElementById('btn-continue-round');
        
        // Show/hide based on current state
        if (this.hasAnswered && this.gameStats.gamesPlayedToday < this.dailyLimit) {
            continueBtn?.classList.remove('hidden');
            nextBtn?.classList.add('hidden');
        } else {
            continueBtn?.classList.add('hidden');
        }
        
        // Update prev/next buttons
        if (prevBtn) {
            prevBtn.disabled = this.currentRoundIndex <= 0;
            prevBtn.style.opacity = prevBtn.disabled ? '0.5' : '1';
        }
        
        if (nextBtn && this.roundHistory.length > 0) {
            const canGoNext = this.currentRoundIndex < this.roundHistory.length - 1;
            nextBtn.disabled = !canGoNext;
            nextBtn.style.opacity = nextBtn.disabled ? '0.5' : '1';
            if (this.hasAnswered && this.currentRoundIndex === this.roundHistory.length - 1) {
                nextBtn.classList.remove('hidden');
            }
        }
    }

    goToPreviousRound() {
        if (this.currentRoundIndex > 0) {
            this.currentRoundIndex--;
            this.loadRoundFromHistory(this.currentRoundIndex);
        }
    }

    goToNextRound() {
        if (this.currentRoundIndex < this.roundHistory.length - 1) {
            this.currentRoundIndex++;
            this.loadRoundFromHistory(this.currentRoundIndex);
        }
    }

    continueToNextRound() {
        this.closeResultModal();
        if (this.gameStats.gamesPlayedToday >= this.dailyLimit) {
            setTimeout(() => this.showLimitReached(), 300);
        } else {
            this.loadNewRound();
        }
    }

    showLimitReached() {
        const gameState = document.getElementById('game-state');
        const limitState = document.getElementById('limit-state');
        const loadingState = document.getElementById('loading-state');
        
        loadingState.classList.add('hidden');
        gameState.classList.add('hidden');
        limitState.classList.remove('hidden');
        
        // Update limit stats
        const accuracy = this.gameStats.totalGames > 0 
            ? Math.round((this.gameStats.totalCorrect / this.gameStats.totalGames) * 100)
            : 0;
        
        document.getElementById('limit-accuracy').textContent = `${accuracy}%`;
        document.getElementById('limit-best-streak').textContent = this.gameStats.bestStreak;
    }

    showError(message) {
        const loadingState = document.getElementById('loading-state');
        loadingState.innerHTML = `
            <div style="color: var(--game-error); font-size: 1.2rem;">
                ⚠️ ${message}
            </div>
            <button class="btn-next" style="margin-top: 20px;" onclick="location.reload()">
                Retry
            </button>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize game when DOM is ready
let game;

document.addEventListener('DOMContentLoaded', () => {
    game = new GameManager();
    
    // Setup event listeners
    const continueBtn = document.getElementById('btn-continue');
    if (continueBtn) {
        continueBtn.addEventListener('click', () => game.closeResultModal());
    }
    
    const continueRoundBtn = document.getElementById('btn-continue-round');
    if (continueRoundBtn) {
        continueRoundBtn.addEventListener('click', () => game.continueToNextRound());
    }
    
    const prevBtn = document.getElementById('btn-prev');
    if (prevBtn) {
        prevBtn.addEventListener('click', () => game.goToPreviousRound());
    }
    
    const nextBtn = document.getElementById('btn-next');
    if (nextBtn) {
        nextBtn.addEventListener('click', () => game.goToNextRound());
    }
    
    const homeBtn = document.getElementById('btn-home');
    if (homeBtn) {
        homeBtn.addEventListener('click', () => {
            window.location.href = '/chat';
        });
    }
});

// Dark/Light mode sync (if theme toggle exists)
function syncTheme() {
    const theme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', theme);
}

// Check theme on load
syncTheme();

// Listen for theme changes
window.addEventListener('storage', (e) => {
    if (e.key === 'theme') {
        syncTheme();
    }
});
