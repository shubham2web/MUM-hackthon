// ATLAS v2.0 Module - Enhanced Analysis
const ATLASv2 = {
    baseURL: 'http://127.0.0.1:8000',

    async analyzeWithV2(claim, options = {}) {
        console.log('🚀 ATLAS v2.0 Analysis Starting...');
        console.log('Claim:', claim);
        console.log('Options:', options);

        try {
            const response = await fetch(`${this.baseURL}/v2/analyze`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    claim: claim,
                    num_agents: options.num_agents || 4,
                    enable_reversal: options.enable_reversal !== false,
                    reversal_rounds: options.reversal_rounds || 1
                })
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`v2.0 API error: ${response.status} - ${errorText}`);
            }

            const data = await response.json();
            console.log('✅ v2.0 Response received:', data);
            
            return {
                success: true,
                data: data
            };

        } catch (error) {
            console.error('❌ v2.0 Analysis Error:', error);
            return {
                success: false,
                error: error.message
            };
        }
    }
};
