// V2 UI Renderer - Creates beautiful v2.0 response cards
const V2UI = {
    createV2ResponseCard(data) {
        const card = document.createElement('div');
        card.className = 'v2-response-card';
        card.style.cssText = `
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(168, 85, 247, 0.1) 100%);
            border: 1px solid rgba(59, 130, 246, 0.3);
            border-radius: 12px;
            padding: 20px;
            margin: 10px 0;
        `;

        let html = '<div style="margin-bottom: 15px;">';
        html += '<h3 style="color: #3b82f6; margin: 0 0 10px 0; font-size: 16px;">🔬 Enhanced Analysis (v2.0)</h3>';
        
        // Credibility Score
        if (data.credibility) {
            const score = data.credibility.overall_score;
            const percentage = (score * 100).toFixed(0);
            const color = score >= 0.75 ? '#10b981' : score >= 0.5 ? '#f59e0b' : '#ef4444';
            
            html += `<div style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px; margin-bottom: 12px;">`;
            html += `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">`;
            html += `<span style="font-weight: 600;">Credibility Score</span>`;
            html += `<span style="color: ${color}; font-weight: bold; font-size: 18px;">${percentage}%</span>`;
            html += `</div>`;
            html += `<div style="background: rgba(255,255,255,0.1); height: 8px; border-radius: 4px; overflow: hidden;">`;
            html += `<div style="background: ${color}; height: 100%; width: ${percentage}%; transition: width 0.5s;"></div>`;
            html += `</div>`;
            html += `<div style="font-size: 12px; color: rgba(255,255,255,0.6); margin-top: 6px;">`;
            html += `Confidence: ${data.credibility.confidence_level}`;
            html += `</div>`;
            html += `</div>`;
        }

        // Synthesis
        if (data.synthesis) {
            html += `<div style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px; margin-bottom: 12px;">`;
            html += `<div style="font-weight: 600; margin-bottom: 8px;">💡 Synthesis</div>`;
            html += `<div style="color: rgba(255,255,255,0.9); line-height: 1.6;">${this.markdownToHtml(data.synthesis)}</div>`;
            html += `</div>`;
        }

        // Role Reversal Results
        if (data.role_reversal && data.role_reversal.rounds && data.role_reversal.rounds.length > 0) {
            html += `<div style="background: rgba(0,0,0,0.2); padding: 12px; border-radius: 8px;">`;
            html += `<div style="font-weight: 600; margin-bottom: 8px;">🔄 Role Reversal Insights</div>`;
            html += `<div style="font-size: 13px; color: rgba(255,255,255,0.8);">`;
            html += `Conducted ${data.role_reversal.rounds.length} reversal round(s) for bias reduction<br>`;
            if (data.role_reversal.convergence) {
                html += `Convergence: ${(data.role_reversal.convergence.convergence_rate * 100).toFixed(1)}%`;
            }
            html += `</div>`;
            html += `</div>`;
        }

        html += '</div>';
        card.innerHTML = html;
        return card;
    },

    markdownToHtml(text) {
        // Simple markdown conversion
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
    }
};
