/**
 * Role Reversal UI Controller
 * 
 * Frontend JavaScript for Phase 2 Role Reversal Support.
 * Handles AJAX calls to /memory/role/* endpoints and renders results.
 */

const RoleReversalUI = {
    baseURL: '/memory',
    
    /**
     * Initialize event listeners when DOM is ready
     */
    init() {
        document.addEventListener('DOMContentLoaded', () => {
            console.log('🔄 Role Reversal UI initialized');
            
            // Button handlers
            const buildBtn = document.getElementById('rr_build_btn');
            const historyBtn = document.getElementById('rr_history_btn');
            const checkBtn = document.getElementById('rr_check_btn');
            
            if (buildBtn) {
                buildBtn.addEventListener('click', () => this.buildReversalContext());
            }
            
            if (historyBtn) {
                historyBtn.addEventListener('click', () => this.showRoleHistory());
            }
            
            if (checkBtn) {
                checkBtn.addEventListener('click', () => this.checkConsistency());
            }
        });
    },
    
    /**
     * Build role reversal context
     */
    async buildReversalContext() {
        const previousRole = document.getElementById('rr_previous_role').value.trim();
        const currentRole = document.getElementById('rr_current_role').value.trim();
        const systemPrompt = document.getElementById('rr_system_prompt').value.trim();
        const currentTask = document.getElementById('rr_current_task').value.trim();
        
        if (!previousRole || !currentRole || !currentTask) {
            this.showError('Please fill in previous role, current role, and current task.');
            return;
        }
        
        const payload = {
            previous_role: previousRole,
            current_role: currentRole,
            system_prompt: systemPrompt || 'You are now switching roles in a debate.',
            current_task: currentTask
        };
        
        try {
            this.showLoading('Building role reversal context...');
            
            const response = await fetch(`${this.baseURL}/role/reversal`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.displayReversalContext(data);
            } else {
                this.showError(`Error: ${data.error || 'Failed to build reversal context'}`);
            }
        } catch (error) {
            this.showError(`Network error: ${error.message}`);
        }
    },
    
    /**
     * Show role history
     */
    async showRoleHistory() {
        const previousRole = document.getElementById('rr_previous_role').value.trim();
        
        if (!previousRole) {
            this.showError('Please enter a role to view history.');
            return;
        }
        
        const payload = { role: previousRole };
        
        try {
            this.showLoading('Fetching role history...');
            
            const response = await fetch(`${this.baseURL}/role/history`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.displayRoleHistory(data);
            } else {
                this.showError(`Error: ${data.error || 'Failed to fetch history'}`);
            }
        } catch (error) {
            this.showError(`Network error: ${error.message}`);
        }
    },
    
    /**
     * Check consistency of new statement
     */
    async checkConsistency() {
        const currentRole = document.getElementById('rr_current_role').value.trim();
        const newStatement = document.getElementById('rr_new_statement').value.trim();
        
        if (!currentRole || !newStatement) {
            this.showError('Please enter current role and new statement.');
            return;
        }
        
        const payload = {
            role: currentRole,
            new_statement: newStatement,
            threshold: 0.3
        };
        
        try {
            this.showLoading('Checking consistency...');
            
            const response = await fetch(`${this.baseURL}/consistency/check`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.displayConsistencyCheck(data);
            } else {
                this.showError(`Error: ${data.error || 'Failed to check consistency'}`);
            }
        } catch (error) {
            this.showError(`Network error: ${error.message}`);
        }
    },
    
    /**
     * Display role reversal context results
     */
    displayReversalContext(data) {
        const previewDiv = document.getElementById('rr_context_preview');
        
        const contextPreview = data.context_payload.substring(0, 800);
        const truncated = data.context_payload.length > 800 ? '...' : '';
        
        previewDiv.innerHTML = `
            <h4>✅ Role Reversal Context Built</h4>
            <p><strong>Role Switch:</strong> ${data.role_switch}</p>
            <p><strong>Previous Arguments Recalled:</strong> ${data.previous_arguments_count}</p>
            <p><strong>Token Estimate:</strong> ~${data.token_estimate} tokens</p>
            <details>
                <summary>📄 Context Preview (click to expand)</summary>
                <pre>${this.escapeHtml(contextPreview)}${truncated}</pre>
            </details>
        `;
        
        // Clear other sections
        document.getElementById('rr_warnings').innerHTML = '';
        document.getElementById('rr_history').innerHTML = '';
    },
    
    /**
     * Display role history
     */
    displayRoleHistory(data) {
        const historyDiv = document.getElementById('rr_history');
        
        if (data.count === 0) {
            historyDiv.innerHTML = `
                <h4>📜 Role History</h4>
                <p>No memories found for role: <strong>${data.role}</strong></p>
            `;
            return;
        }
        
        let html = `
            <h4>📜 Role History for "${data.role}" (${data.count} memories)</h4>
            <ul class="history-list">
        `;
        
        data.memories.slice(0, 10).forEach((memory, idx) => {
            const content = memory.content.substring(0, 100);
            const truncated = memory.content.length > 100 ? '...' : '';
            const turn = memory.metadata?.turn || '?';
            
            html += `
                <li>
                    <strong>Turn ${turn}:</strong> ${this.escapeHtml(content)}${truncated}
                </li>
            `;
        });
        
        if (data.count > 10) {
            html += `<li><em>... and ${data.count - 10} more</em></li>`;
        }
        
        html += '</ul>';
        historyDiv.innerHTML = html;
        
        // Clear other sections
        document.getElementById('rr_warnings').innerHTML = '';
        document.getElementById('rr_context_preview').innerHTML = '';
    },
    
    /**
     * Display consistency check results
     */
    displayConsistencyCheck(data) {
        const warningsDiv = document.getElementById('rr_warnings');
        
        let html = '<h4>🔍 Consistency Check</h4>';
        
        if (data.has_inconsistencies) {
            html += `
                <div class="alert alert-warning">
                    <p><strong>⚠️ Potential Contradictions Detected</strong></p>
                    <p><strong>Consistency Score:</strong> ${data.consistency_score.toFixed(2)}</p>
                    <ul>
            `;
            
            data.warnings.forEach(warning => {
                html += `<li>${this.escapeHtml(warning)}</li>`;
            });
            
            html += '</ul></div>';
            
            if (data.related_statements && data.related_statements.length > 0) {
                html += '<h5>Related Statements:</h5><ul>';
                data.related_statements.forEach(stmt => {
                    const content = stmt.text.substring(0, 100);
                    html += `<li>${this.escapeHtml(content)}... (score: ${stmt.score.toFixed(2)})</li>`;
                });
                html += '</ul>';
            }
        } else {
            html += `
                <div class="alert alert-success">
                    <p><strong>✅ No Contradictions Detected</strong></p>
                    <p><strong>Consistency Score:</strong> ${data.consistency_score.toFixed(2)}</p>
                </div>
            `;
        }
        
        warningsDiv.innerHTML = html;
        
        // Clear other sections
        document.getElementById('rr_history').innerHTML = '';
        document.getElementById('rr_context_preview').innerHTML = '';
    },
    
    /**
     * Show loading message
     */
    showLoading(message) {
        const resultsDiv = document.getElementById('rr_results');
        resultsDiv.innerHTML = `
            <div class="loading">
                <div class="spinner"></div>
                <p>${message}</p>
            </div>
        `;
    },
    
    /**
     * Show error message
     */
    showError(message) {
        const resultsDiv = document.getElementById('rr_results');
        resultsDiv.innerHTML = `
            <div class="alert alert-error">
                <p><strong>❌ Error:</strong> ${this.escapeHtml(message)}</p>
            </div>
        `;
    },
    
    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Initialize when script loads
RoleReversalUI.init();
