/**
 * ATLAS v2.0 Frontend Integration
 * Connects chat interface to enhanced v2.0 analysis features
 */

const ATLASv2 = {
    baseURL: window.location.origin,  // Use same origin as page (dynamic port)
    isAnalyzing: false,

    /**
     * Run full v2.0 analysis with enhanced features
     * @param {string} claim - The claim to analyze
     * @param {object} options - Analysis options
     * @param {AbortSignal} externalSignal - External abort signal from caller
     */
    async analyzeWithV2(claim, options = {}, externalSignal = null) {
        const {
            num_agents = 4,
            enable_reversal = false,
            reversal_rounds = 1
        } = options;

        try {
            console.log('🚀 Starting ATLAS v2.0 analysis...');
            
            // Use AbortController for timeout (5 minutes for complex analysis)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 300000);  // 5 min timeout
            
            // If external signal is provided, link it to our controller
            if (externalSignal) {
                externalSignal.addEventListener('abort', () => {
                    console.log('🛑 External abort signal received in ATLASv2');
                    clearTimeout(timeoutId);
                    controller.abort();
                });
                
                // Check if already aborted
                if (externalSignal.aborted) {
                    clearTimeout(timeoutId);
                    throw new DOMException('Aborted by user', 'AbortError');
                }
            }
            
            const response = await fetch(`${this.baseURL}/v2/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    claim,
                    num_agents,
                    enable_reversal,
                    reversal_rounds
                }),
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('✅ v2.0 Analysis complete:', data);
            
            // Return in expected format for index.html
            return {
                success: true,
                data: data.result || data
            };

        } catch (error) {
            console.error('❌ v2.0 Analysis error:', error);
            if (error.name === 'AbortError') {
                return {
                    success: false,
                    error: 'Analysis timed out. The API may be rate-limited. Try again in a minute or disable v2.0 for faster results.'
                };
            }
            return {
                success: false,
                error: error.message || 'v2.0 analysis failed'
            };
        }
    },

    /**
     * Get quick credibility score without full analysis
     */
    async getCredibilityScore(claim, sources, evidenceTexts) {
        try {
            const response = await fetch(`${this.baseURL}/v2/credibility`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    claim,
                    sources,
                    evidence_texts: evidenceTexts
                })
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            return await response.json();
        } catch (error) {
            console.error('Credibility check error:', error);
            throw error;
        }
    },

    /**
     * Get available agent roles for display
     */
    async getRoles(topic = '') {
        try {
            const url = topic 
                ? `${this.baseURL}/v2/roles?topic=${encodeURIComponent(topic)}`
                : `${this.baseURL}/v2/roles`;
            
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const data = await response.json();
            return data.roles || [];
        } catch (error) {
            console.error('Get roles error:', error);
            return [];
        }
    },

    /**
     * Get bias report for transparency
     */
    async getBiasReport(entity = null) {
        try {
            const url = entity 
                ? `${this.baseURL}/v2/bias-report?entity=${encodeURIComponent(entity)}`
                : `${this.baseURL}/v2/bias-report`;
            
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            return await response.json();
        } catch (error) {
            console.error('Bias report error:', error);
            return null;
        }
    }
};

/**
 * UI Components for v2.0 features
 */
const V2UI = {
    /**
     * Create credibility score badge
     */
    createCredibilityBadge(credibilityScore) {
        const { overall, confidence_level, explanation, warnings } = credibilityScore;
        const percentage = Math.round(overall * 100);
        
        let badgeClass = 'credibility-low';
        let badgeIcon = '❌';
        
        if (overall >= 0.75) {
            badgeClass = 'credibility-high';
            badgeIcon = '✅';
        } else if (overall >= 0.5) {
            badgeClass = 'credibility-medium';
            badgeIcon = '⚠️';
        }

        return `
            <div class="credibility-container ${badgeClass}">
                <div class="credibility-header">
                    <span class="credibility-icon">${badgeIcon}</span>
                    <span class="credibility-label">Credibility Score</span>
                </div>
                <div class="credibility-score">${percentage}%</div>
                <div class="credibility-confidence">${confidence_level} Confidence</div>
                ${warnings && warnings.length > 0 ? `
                    <div class="credibility-warnings">
                        ${warnings.map(w => `<div class="warning-item">⚠️ ${w}</div>`).join('')}
                    </div>
                ` : ''}
                <div class="credibility-details">
                    <button class="details-btn" onclick="V2UI.showCredibilityDetails(${JSON.stringify(credibilityScore).replace(/"/g, '&quot;')})">
                        View Details
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Create evidence sources display
     */
    createEvidenceSection(evidence) {
        const { total_sources, sources } = evidence;
        
        if (!sources || sources.length === 0) {
            return '<div class="evidence-none">No sources available</div>';
        }

        return `
            <div class="evidence-container">
                <div class="evidence-header">
                    <span class="evidence-icon">📚</span>
                    <span class="evidence-label">Evidence Sources (${total_sources})</span>
                </div>
                <div class="evidence-list">
                    ${sources.slice(0, 5).map(source => `
                        <div class="evidence-item">
                            <div class="evidence-domain">${this.escapeHtml(source.domain)}</div>
                            <div class="evidence-trust">Trust: ${Math.round(source.trust_score * 100)}%</div>
                            <a href="${this.escapeHtml(source.url)}" target="_blank" class="evidence-link">
                                View Source →
                            </a>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    },

    /**
     * Create bias audit summary
     */
    createBiasSection(biasAudit) {
        const { total_flags, bias_type_distribution } = biasAudit;
        
        if (total_flags === 0) {
            return `
                <div class="bias-container bias-none">
                    <div class="bias-header">
                        <span class="bias-icon">✅</span>
                        <span class="bias-label">No Bias Detected</span>
                    </div>
                </div>
            `;
        }

        const topBiases = Object.entries(bias_type_distribution || {})
            .sort((a, b) => b[1] - a[1])
            .slice(0, 3);

        return `
            <div class="bias-container">
                <div class="bias-header">
                    <span class="bias-icon">🔍</span>
                    <span class="bias-label">Bias Audit</span>
                </div>
                <div class="bias-count">${total_flags} flag${total_flags !== 1 ? 's' : ''} detected</div>
                ${topBiases.length > 0 ? `
                    <div class="bias-list">
                        ${topBiases.map(([type, count]) => `
                            <div class="bias-item">
                                <span class="bias-type">${this.formatBiasType(type)}</span>
                                <span class="bias-count-badge">${count}</span>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    },

    /**
     * Create role reversal results (if enabled)
     */
    createReversalSection(roleReversal) {
        if (!roleReversal.enabled || !roleReversal.convergence) {
            return '';
        }

        const { convergence } = roleReversal;
        const convergencePercent = Math.round((1 - convergence.final_divergence) * 100);

        return `
            <div class="reversal-container">
                <div class="reversal-header">
                    <span class="reversal-icon">🔄</span>
                    <span class="reversal-label">Role Reversal Analysis</span>
                </div>
                <div class="reversal-convergence">
                    <div class="convergence-label">Convergence Rate</div>
                    <div class="convergence-bar">
                        <div class="convergence-fill" style="width: ${convergencePercent}%"></div>
                    </div>
                    <div class="convergence-percent">${convergencePercent}%</div>
                </div>
                <div class="reversal-consensus ${convergence.stable_consensus ? 'consensus-yes' : 'consensus-no'}">
                    ${convergence.stable_consensus ? '✅ Consensus Reached' : '⚠️ No Consensus'}
                </div>
            </div>
        `;
    },

    /**
     * Create complete v2.0 response card - NOW USES v2.5 DASHBOARD
     */
    createV2ResponseCard(result) {
        // Use the new v2.5 professional dashboard if available
        if (window.ATLASv25 && typeof window.ATLASv25.renderDashboard === 'function') {
            return window.ATLASv25.renderDashboard(result);
        }
        
        // Fallback to basic v2.0 card
        const { credibility_score, evidence, bias_audit, role_reversal, synthesis } = result;

        return `
            <div class="v2-response-card">
                <div class="v2-header">
                    <span class="v2-badge">ATLAS v2.0</span>
                    <span class="v2-duration">${result.duration_seconds?.toFixed(1)}s</span>
                </div>
                
                ${this.createCredibilityBadge(credibility_score)}
                
                <div class="v2-sections">
                    ${this.createEvidenceSection(evidence)}
                    ${this.createBiasSection(bias_audit)}
                    ${this.createReversalSection(role_reversal)}
                </div>

                ${synthesis ? `
                    <div class="synthesis-container">
                        <div class="synthesis-header">📊 Analysis Summary</div>
                        <div class="synthesis-content">${this.formatMarkdown(synthesis)}</div>
                    </div>
                ` : ''}
            </div>
        `;
    },

    /**
     * Show detailed credibility breakdown in modal
     */
    showCredibilityDetails(credibilityScore) {
        const modal = document.createElement('div');
        modal.className = 'v2-modal-overlay';
        modal.innerHTML = `
            <div class="v2-modal-content">
                <div class="v2-modal-header">
                    <h2>Credibility Score Details</h2>
                    <button class="v2-modal-close" onclick="this.closest('.v2-modal-overlay').remove()">×</button>
                </div>
                <div class="v2-modal-body">
                    <div class="metric-row">
                        <span class="metric-label">Source Trust</span>
                        <span class="metric-bar">
                            <span class="metric-fill" style="width: ${credibilityScore.source_trust * 100}%"></span>
                        </span>
                        <span class="metric-value">${Math.round(credibilityScore.source_trust * 100)}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Evidence Alignment</span>
                        <span class="metric-bar">
                            <span class="metric-fill" style="width: ${credibilityScore.semantic_alignment * 100}%"></span>
                        </span>
                        <span class="metric-value">${Math.round(credibilityScore.semantic_alignment * 100)}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Temporal Consistency</span>
                        <span class="metric-bar">
                            <span class="metric-fill" style="width: ${credibilityScore.temporal_consistency * 100}%"></span>
                        </span>
                        <span class="metric-value">${Math.round(credibilityScore.temporal_consistency * 100)}%</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Source Diversity</span>
                        <span class="metric-bar">
                            <span class="metric-fill" style="width: ${credibilityScore.evidence_diversity * 100}%"></span>
                        </span>
                        <span class="metric-value">${Math.round(credibilityScore.evidence_diversity * 100)}%</span>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Close on background click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    },

    // Helper functions
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    formatMarkdown(text) {
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    },

    formatBiasType(type) {
        return type.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    }
};

// Export for global use
window.ATLASv2 = ATLASv2;
window.V2UI = V2UI;
