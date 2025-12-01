/**
 * ATLAS v2.5 Intelligence Dashboard
 * Professional-grade analysis visualization module
 */

const ATLASv25 = {
    /**
     * Generate the complete v2.5 Intelligence Dashboard HTML
     * @param {Object} data - The analysis response data
     * @returns {string} - Complete HTML for the dashboard
     */
    renderDashboard(data) {
        // Extract data with defaults
        const synthesis = data.synthesis || data.summary || '';
        const credibility = data.credibility_score || data.credibility || {};
        const biasAudit = data.bias_audit || {};
        const roleReversal = data.role_reversal || {};
        const debate = data.debate_insights || data.debate || {};
        const duration = data.duration_seconds || 0;

        return `
            <div class="atlas-v25-dashboard">
                ${this.renderGradientDefs()}
                ${this.renderHeader(duration)}
                ${this.renderAnalysisTarget(data)}
                ${this.renderCredibilityPanel(credibility)}
                ${this.renderRoleReversalAnalysis(roleReversal)}
                ${this.renderBiasAudit(biasAudit)}
                ${this.renderFinalVerdict(credibility)}
            </div>
        `;
    },

    /**
     * SVG Gradient definitions for score rings
     */
    renderGradientDefs() {
        return `
            <svg class="v25-gradients" aria-hidden="true">
                <defs>
                    <linearGradient id="scoreGradientHigh" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" style="stop-color:#10b981" />
                        <stop offset="100%" style="stop-color:#34d399" />
                    </linearGradient>
                    <linearGradient id="scoreGradientMedium" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" style="stop-color:#f59e0b" />
                        <stop offset="100%" style="stop-color:#fbbf24" />
                    </linearGradient>
                    <linearGradient id="scoreGradientLow" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" style="stop-color:#ef4444" />
                        <stop offset="100%" style="stop-color:#f87171" />
                    </linearGradient>
                </defs>
            </svg>
        `;
    },

    /**
     * Dashboard Header
     */
    renderHeader(duration) {
        return `
            <div class="v25-header">
                <div class="v25-title-section">
                    <div class="v25-logo">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.5 3-9s-1.343-9-3-9m-9 9a9 9 0 019 9m-9-9a9 9 0 009-9m-9 9h12"/>
                        </svg>
                    </div>
                    <div>
                        <div class="v25-title">ATLAS v2.5 Intelligence Report</div>
                        <div class="v25-subtitle">Enhanced Analysis Dashboard</div>
                    </div>
                </div>
                <div class="v25-meta">
                    <span class="v25-version-badge">v2.5</span>
                    ${duration ? `<span class="v25-duration">⏱️ ${duration.toFixed(1)}s</span>` : ''}
                </div>
            </div>
        `;
    },

    /**
     * Analysis Target - Just show the URL being analyzed
     */
    renderAnalysisTarget(data) {
        const synthesis = data.synthesis || data.summary || '';
        
        // Extract URL from synthesis if present
        const urlMatch = synthesis.match(/(https?:\/\/[^\s]+)/);
        const url = urlMatch ? urlMatch[1] : null;
        
        if (!url) return '';
        
        // Get domain from URL
        let domain = '';
        try {
            domain = new URL(url).hostname;
        } catch (e) {
            domain = url;
        }

        return `
            <div class="v25-target-panel">
                <div class="v25-target-icon">🔍</div>
                <div class="v25-target-info">
                    <div class="v25-target-label">Analyzing</div>
                    <a href="${this.escapeHtml(url)}" target="_blank" class="v25-target-url">${this.escapeHtml(domain)}</a>
                </div>
            </div>
        `;
    },

    /**
     * Format synthesis content with proper structure
     */
    formatSynthesisContent(synthesis, credibility) {
        // If synthesis contains URL reference, format it nicely
        let content = synthesis;
        
        // Highlight URLs
        content = content.replace(
            /(https?:\/\/[^\s]+)/g, 
            '<span style="color: #00d4ff; word-break: break-all;">$1</span>'
        );
        
        // Format markdown-style bold
        content = content.replace(/\*\*(.*?)\*\*/g, '<strong style="color: #fff;">$1</strong>');
        
        // Format line breaks
        content = content.replace(/\n/g, '<br>');
        
        return content;
    },

    /**
     * Credibility Assessment Panel
     */
    renderCredibilityPanel(credibility) {
        const overall = credibility.overall || credibility.score || 0;
        const percentage = Math.round(overall * 100);
        const sourceTrust = Math.round((credibility.source_trust || 0) * 100);
        const alignment = Math.round((credibility.semantic_alignment || credibility.evidence_alignment || 0) * 100);
        const temporal = Math.round((credibility.temporal_consistency || 1) * 100);
        const diversity = Math.round((credibility.evidence_diversity || credibility.source_diversity || 0.33) * 100);

        const scoreClass = percentage >= 70 ? 'high' : percentage >= 40 ? 'medium' : 'low';
        const circumference = 2 * Math.PI * 60; // radius = 60
        const dashOffset = circumference - (percentage / 100) * circumference;

        return `
            <div class="v25-panel">
                <div class="v25-panel-header">
                    <div class="v25-panel-icon">📊</div>
                    <div class="v25-panel-title">Credibility Assessment</div>
                </div>
                <div class="v25-panel-content">
                    <div class="v25-credibility-panel">
                        <div class="v25-score-circle">
                            <svg class="v25-score-ring" viewBox="0 0 140 140">
                                <circle class="v25-score-ring-bg" cx="70" cy="70" r="60"/>
                                <circle 
                                    class="v25-score-ring-fill ${scoreClass}" 
                                    cx="70" cy="70" r="60"
                                    stroke-dasharray="${circumference}"
                                    stroke-dashoffset="${dashOffset}"
                                />
                            </svg>
                            <div class="v25-score-value">
                                <div class="v25-score-number">${percentage}%</div>
                                <div class="v25-score-label">${credibility.confidence_level || this.getConfidenceLevel(percentage)}</div>
                            </div>
                        </div>
                        <div class="v25-metrics-grid">
                            ${this.renderMetricBar('Source Trust', sourceTrust)}
                            ${this.renderMetricBar('Evidence Alignment', alignment)}
                            ${this.renderMetricBar('Temporal Consistency', temporal)}
                            ${this.renderMetricBar('Source Diversity', diversity)}
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Evidence Influence Map
     * Accepts an array of {source, weight} and renders a simple proportional-node SVG map.
     */
    renderEvidenceInfluence(data) {
        const list = data && (data.evidence_influence || data.influence || data) || [];
        if (!Array.isArray(list) || list.length === 0) {
            return `
                <div class="v25-panel">
                    <div class="v25-panel-header">
                        <div class="v25-panel-icon">🗺️</div>
                        <div class="v25-panel-title">Evidence Influence Map</div>
                    </div>
                    <div class="v25-panel-content">
                        <div class="v25-no-data">No influence data available</div>
                    </div>
                </div>
            `;
        }

        // Normalize and sort by weight
        const nodes = list.map((n, i) => ({
            id: i,
            label: n.source || n.name || `Source ${i+1}`,
            weight: Math.max(0, Number(n.weight) || 0)
        })).sort((a,b)=> b.weight - a.weight);

        // Total for scaling
        const total = nodes.reduce((s,n)=> s + n.weight, 0) || 1;

        // Generate simple SVG circles laid out horizontally
        const svgParts = nodes.map((node, idx) => {
            const radius = Math.max(18, Math.min(64, (node.weight / total) * 120));
            const cx = 80 + idx * 120;
            const cy = 70;
            const fill = idx === 0 ? 'url(#scoreGradientHigh)' : (node.weight / total > 0.25 ? 'url(#scoreGradientMedium)' : 'url(#scoreGradientLow)');
            return `
                <g class="v25-evidence-node" data-label="${this.escapeHtml(node.label)}" data-weight="${node.weight}">
                    <circle cx="${cx}" cy="${cy}" r="${radius}" fill="${fill}" opacity="0.95" stroke="rgba(255,255,255,0.06)" />
                    <text x="${cx}" y="${cy + radius + 14}" text-anchor="middle" fill="rgba(255,255,255,0.8)" font-size="12">${this.escapeHtml(node.label)}</text>
                    <text x="${cx}" y="${cy + radius + 30}" text-anchor="middle" fill="rgba(255,255,255,0.5)" font-size="11">${Math.round(node.weight * 100)}%</text>
                </g>
            `;
        }).join('');

        return `
            <div class="v25-panel">
                <div class="v25-panel-header">
                    <div class="v25-panel-icon">🗺️</div>
                    <div class="v25-panel-title">Evidence Influence Map</div>
                </div>
                <div class="v25-panel-content">
                    <div class="v25-evidence-map">
                        <svg viewBox="0 0 ${Math.max(400, nodes.length * 120)} 180" preserveAspectRatio="xMidYMid meet">
                            ${this.renderGradientDefs()}
                            ${svgParts}
                        </svg>
                        <div class="v25-evidence-hint">Circle size = relative influence weight. Click nodes for source link (if available).</div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Radar Chart Panel (simple SVG radar using credibility axes)
     */
    renderRadarChart(credibility) {
        if (!credibility) return '';
        const axes = [
            {label: 'Source Trust', value: (credibility.source_trust || 0)},
            {label: 'Alignment', value: (credibility.semantic_alignment || credibility.evidence_alignment || 0)},
            {label: 'Diversity', value: (credibility.evidence_diversity || credibility.source_diversity || 0)},
            {label: 'Temporal', value: (credibility.temporal_consistency || 0)},
            {label: 'Spread', value: (credibility.evidence_spread || 0)}
        ];

        const cx = 120, cy = 120, radius = 80; // svg center
        const points = axes.map((a, i) => {
            const angle = (Math.PI * 2 * i) / axes.length - Math.PI / 2;
            const r = (a.value || 0) * radius;
            return `${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`;
        }).join(' ');

        const axisLines = axes.map((a, i) => {
            const angle = (Math.PI * 2 * i) / axes.length - Math.PI / 2;
            const x = cx + radius * Math.cos(angle);
            const y = cy + radius * Math.sin(angle);
            return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`;
        }).join('');

        const labels = axes.map((a, i) => {
            const angle = (Math.PI * 2 * i) / axes.length - Math.PI / 2;
            const x = cx + (radius + 20) * Math.cos(angle);
            const y = cy + (radius + 20) * Math.sin(angle) + 4;
            return `<text x="${x}" y="${y}" fill="rgba(255,255,255,0.7)" font-size="11" text-anchor="middle">${this.escapeHtml(a.label)}</text>`;
        }).join('');

        return `
            <div class="v25-panel">
                <div class="v25-panel-header">
                    <div class="v25-panel-icon">📡</div>
                    <div class="v25-panel-title">Credibility Radar</div>
                </div>
                <div class="v25-panel-content" style="display:flex; justify-content:center;">
                    <svg viewBox="0 0 240 240" width="240" height="240">
                        <g transform="translate(0,0)">
                            ${axisLines}
                            <polygon points="${points}" fill="rgba(0,212,255,0.12)" stroke="rgba(0,212,255,0.35)" stroke-width="1.5" />
                            ${labels}
                        </g>
                    </svg>
                </div>
            </div>
        `;
    },

    /**
     * Get dynamic gradient color based on percentage (0-100)
     * Returns CSS linear-gradient from red (0%) through yellow (50%) to green (100%)
     */
    getGradientColor(value) {
        // Clamp value between 0 and 100
        const v = Math.max(0, Math.min(100, value));
        
        // Calculate RGB: red (low) → yellow (mid) → green (high)
        let r, g, b = 50; // slight blue tint for depth
        
        if (v <= 50) {
            // Red to Yellow (0-50)
            r = 239; // keep red high
            g = Math.round(68 + (v / 50) * (180 - 68)); // 68 → 180
        } else {
            // Yellow to Green (50-100)
            r = Math.round(239 - ((v - 50) / 50) * (239 - 34)); // 239 → 34
            g = Math.round(180 + ((v - 50) / 50) * (211 - 180)); // 180 → 211
        }
        
        // Create gradient with slight lighter shade for depth
        const lighterR = Math.min(255, r + 30);
        const lighterG = Math.min(255, g + 30);
        
        return `linear-gradient(90deg, rgb(${r}, ${g}, ${b}), rgb(${lighterR}, ${lighterG}, ${b + 20}))`;
    },

    /**
     * Render a single metric bar with dynamic red-to-green gradient
     */
    renderMetricBar(label, value) {
        const gradientStyle = this.getGradientColor(value);
        return `
            <div class="v25-metric-row">
                <span class="v25-metric-label">${label}</span>
                <div class="v25-metric-bar">
                    <div class="v25-metric-fill-dynamic" style="width: ${value}%; background: ${gradientStyle};"></div>
                </div>
                <span class="v25-metric-value">${value}%</span>
            </div>
        `;
    },

    /**
     * Debate Insights Panel
     */
    renderDebateInsights(debate, roleReversal) {
        const participants = roleReversal.participants || debate.participants || 
            ['Proponent', 'Opponent', 'Scientific Analyst', 'Fact Checker'];
        const rounds = roleReversal.rounds_conducted || debate.rounds || 1;

        return `
            <div class="v25-panel">
                <div class="v25-panel-header">
                    <div class="v25-panel-icon">⚔️</div>
                    <div class="v25-panel-title">Debate Insights</div>
                </div>
                <div class="v25-panel-content">
                    <div class="v25-participants">
                        <div class="v25-participants-label">Participants</div>
                        <div class="v25-participant-tags">
                            ${participants.map(p => `
                                <span class="v25-participant-tag">${this.escapeHtml(p)}</span>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Role Reversal Analysis Panel with visual bars
     */
    renderRoleReversalAnalysis(roleReversal) {
        if (!roleReversal.enabled && !roleReversal.convergence) {
            return '';
        }

        const convergence = roleReversal.convergence || {};
        const initialDiv = Math.round((convergence.initial_divergence || 0) * 100);
        const finalDiv = Math.round((convergence.final_divergence || 0) * 100);
        const rate = convergence.convergence_rate || 0;
        const ratePercent = Math.abs(rate * 100);
        const consensus = convergence.stable_consensus;

        // For divergence: lower is better (invert for color: 100-value)
        const initialDivColor = this.getGradientColor(100 - initialDiv);
        const finalDivColor = this.getGradientColor(100 - finalDiv);

        return `
            <div class="v25-panel">
                <div class="v25-panel-header">
                    <div class="v25-panel-icon">🔄</div>
                    <div class="v25-panel-title">Role Reversal Analysis</div>
                </div>
                <div class="v25-panel-content">
                    <div class="v25-reversal-visual-stats">
                        <div class="v25-reversal-visual-stat">
                            <div class="v25-reversal-stat-header">
                                <span class="v25-reversal-stat-label">Initial Divergence</span>
                                <span class="v25-reversal-stat-value">${initialDiv}%</span>
                            </div>
                            <div class="v25-metric-bar">
                                <div class="v25-metric-fill-dynamic" style="width: ${initialDiv}%; background: ${initialDivColor};"></div>
                            </div>
                        </div>
                        <div class="v25-reversal-visual-stat">
                            <div class="v25-reversal-stat-header">
                                <span class="v25-reversal-stat-label">Final Divergence</span>
                                <span class="v25-reversal-stat-value">${finalDiv}%</span>
                            </div>
                            <div class="v25-metric-bar">
                                <div class="v25-metric-fill-dynamic" style="width: ${finalDiv}%; background: ${finalDivColor};"></div>
                            </div>
                        </div>
                        <div class="v25-reversal-visual-stat">
                            <div class="v25-reversal-stat-header">
                                <span class="v25-reversal-stat-label">Convergence Rate</span>
                                <span class="v25-reversal-stat-value">${rate.toFixed(3)}</span>
                            </div>
                        </div>
                        <div class="v25-reversal-visual-stat">
                            <div class="v25-reversal-stat-header">
                                <span class="v25-reversal-stat-label">Consensus Reached</span>
                                <span class="v25-consensus-badge ${consensus ? 'yes' : 'no'}">
                                    ${consensus ? '✅ Yes' : '⚠️ No'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Bias Audit Panel
     */
    renderBiasAudit(biasAudit) {
        const totalFlags = biasAudit.total_flags || 0;
        const entities = biasAudit.entities_monitored || 0;
        const distribution = biasAudit.bias_type_distribution || {};

        if (totalFlags === 0) {
            return `
                <div class="v25-panel">
                    <div class="v25-panel-header">
                        <div class="v25-panel-icon">🛡️</div>
                        <div class="v25-panel-title">Bias Audit</div>
                    </div>
                    <div class="v25-panel-content">
                        <div class="v25-no-data">
                            <div class="v25-no-data-icon">✅</div>
                            <div>No significant bias detected</div>
                        </div>
                    </div>
                </div>
            `;
        }

        const biasTypes = Object.entries(distribution)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5);

        return `
            <div class="v25-panel">
                <div class="v25-panel-header">
                    <div class="v25-panel-icon">🛡️</div>
                    <div class="v25-panel-title">Bias Audit</div>
                </div>
                <div class="v25-panel-content">
                    <div class="v25-bias-summary">
                        <div class="v25-bias-stat">
                            <div class="v25-bias-stat-value">${totalFlags}</div>
                            <div class="v25-bias-stat-label">Total Bias Flags</div>
                        </div>
                        <div class="v25-bias-stat">
                            <div class="v25-bias-stat-value">${entities}</div>
                            <div class="v25-bias-stat-label">Entities Monitored</div>
                        </div>
                    </div>
                    ${biasTypes.length > 0 ? `
                        <div class="v25-bias-types">
                            <div class="v25-bias-types-header">Most Common Biases</div>
                            <div class="v25-bias-chips">
                                ${biasTypes.map(([type, count]) => `
                                    <span class="v25-bias-chip ${count > 2 ? 'caution' : 'warning'}">
                                        ${this.formatBiasType(type)}
                                        <span class="chip-count">${count}</span>
                                    </span>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;
    },

    /**
     * Final Verdict Panel
     */
    renderFinalVerdict(credibility) {
        const overall = credibility.overall || credibility.score || 0;
        const percentage = Math.round(overall * 100);
        
        let verdictText, verdictClass, verdictIcon;
        
        if (percentage >= 80) {
            verdictText = 'HIGHLY CREDIBLE';
            verdictClass = 'high';
            verdictIcon = '🟢';
        } else if (percentage >= 60) {
            verdictText = 'CREDIBLE';
            verdictClass = 'good';
            verdictIcon = '🔵';
        } else if (percentage >= 40) {
            verdictText = 'MODERATELY CREDIBLE';
            verdictClass = 'moderate';
            verdictIcon = '🟡';
        } else {
            verdictText = 'LOW CREDIBILITY';
            verdictClass = 'low';
            verdictIcon = '🔴';
        }

        const explanation = credibility.explanation || this.getVerdictReason(percentage);

        return `
            <div class="v25-verdict-panel">
                <div class="v25-verdict-header">
                    <div class="v25-panel-icon">⚖️</div>
                    <div class="v25-panel-title">Final Verdict</div>
                </div>
                <div class="v25-verdict-content">
                    <div class="v25-verdict-indicator">
                        <span class="v25-verdict-icon">${verdictIcon}</span>
                        <span class="v25-verdict-text ${verdictClass}">${verdictText}</span>
                    </div>
                    <div class="v25-verdict-confidence">
                        Confidence: <span>${percentage}%</span>
                    </div>
                    <div class="v25-verdict-reason">
                        ${this.escapeHtml(explanation)}
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Role Reversal Insights (bottom summary)
     */
    renderRoleReversalInsights(roleReversal) {
        if (!roleReversal.enabled && !roleReversal.rounds_conducted) {
            return '';
        }

        const rounds = roleReversal.rounds_conducted || 1;
        const convergence = roleReversal.convergence || {};
        const rate = convergence.convergence_rate || 0;
        const convergencePercent = Math.round((1 - (convergence.final_divergence || 1)) * 100);

        return `
            <div class="v25-panel v25-insights-panel">
                <div class="v25-panel-header">
                    <div class="v25-panel-icon">📈</div>
                    <div class="v25-panel-title">Role Reversal Insights</div>
                </div>
                <div class="v25-insights-content">
                    <div class="v25-insight-row">
                        <span class="v25-insight-label">Conducted ${rounds} reversal round${rounds !== 1 ? 's' : ''} for bias reduction</span>
                    </div>
                    <div class="v25-insight-row">
                        <span class="v25-insight-label">Convergence</span>
                        <span class="v25-insight-value">${(rate * 100).toFixed(1)}%</span>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Helper: Get confidence level text
     */
    getConfidenceLevel(percentage) {
        if (percentage >= 80) return 'High Confidence';
        if (percentage >= 60) return 'Good Confidence';
        if (percentage >= 40) return 'Medium Confidence';
        return 'Low Confidence';
    },

    /**
     * Helper: Get verdict reason based on score
     */
    getVerdictReason(percentage) {
        if (percentage >= 80) return 'Strong evidence alignment with high source diversity';
        if (percentage >= 60) return 'Good evidence support with reasonable verification';
        if (percentage >= 40) return 'Mixed evidence, exercise caution';
        return 'Limited evidence or significant credibility concerns';
    },

    /**
     * Helper: Format bias type names
     */
    formatBiasType(type) {
        return type.split('_').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1)
        ).join(' ');
    },

    /**
     * Helper: Escape HTML
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Export for global use
window.ATLASv25 = ATLASv25;
