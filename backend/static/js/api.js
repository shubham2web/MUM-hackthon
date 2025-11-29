// API Module with detailed logging
const API = {
    baseURL: 'http://127.0.0.1:8000', // Backend server port

    async sendMessage(message, mode = 'analytical', conversationHistory = []) {
        console.log('=== API Call (ATLAS v4.1 Verdict Engine) ===');
        console.log('Message:', message);
        console.log('Mode:', mode);
        console.log('Conversation History:', conversationHistory);
        
        // Get or create session_id from localStorage for conversation continuity
        let sessionId = localStorage.getItem('atlas-session-id');
        if (!sessionId) {
            sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('atlas-session-id', sessionId);
        }
        
        try {
            // Use /rag/debate for debate mode (with thinking trace), /analyze for standard
            const endpoint = mode === 'debate' 
                ? `${this.baseURL}/rag/debate` 
                : `${this.baseURL}/analyze_topic`;
            
            const requestBody = mode === 'debate' ? {
                claim: message,
                session_id: sessionId,
                enable_forensics: true
            } : {
                topic: message,
                model: 'llama3',
                mode: mode,
                session_id: sessionId,
                conversation_history: conversationHistory
            };
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            
            console.log('Response status:', response.status);
            console.log('Response ok:', response.ok);
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
            }
            
            // Check if it's an SSE stream (old debate mode - shouldn't happen with v4.1)
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('text/event-stream')) {
                return { isStream: true, response: response };
            }
            
            // Regular JSON response - includes verdict for debate mode
            const responseText = await response.text();
            console.log('Response text:', responseText);
            const data = JSON.parse(responseText);
            console.log('Parsed data:', data);
            
            // For debate mode, return structured response with trace
            if (mode === 'debate') {
                return { 
                    isDebate: true, 
                    trace: data.trace || [],
                    pro: data.pro,
                    opp: data.opp,
                    verdict: data.verdict,
                    evidence: data.evidence || []
                };
            }
            
            return data;
            
        } catch (error) {
            console.error('=== API Error ===');
            console.error('Error details:', error);
            throw error;
        }
    }
};
