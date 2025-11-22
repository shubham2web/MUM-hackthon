// API Module with detailed logging
const API = {
    baseURL: 'http://127.0.0.1:8000', // Backend server port

    async sendMessage(message, mode = 'analytical', conversationHistory = []) {
        console.log('=== API Call ===');
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
            const response = await fetch(`${this.baseURL}/analyze_topic`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    topic: message, 
                    model: 'llama3',
                    mode: mode,  // Send mode parameter to backend
                    session_id: sessionId,  // Send session ID for memory context
                    conversation_history: conversationHistory  // Send full conversation
                })
            });
            
            console.log('Response status:', response.status);
            console.log('Response ok:', response.ok);
            
            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`HTTP error! status: ${response.status}, body: ${errorText}`);
            }
            
            // Check if it's an SSE stream (debate mode)
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('text/event-stream')) {
                // Return response for SSE streaming
                return { isStream: true, response: response };
            }
            
            // Regular JSON response (analytical mode)
            const responseText = await response.text();
            console.log('Response text:', responseText);
            const data = JSON.parse(responseText);
            console.log('Parsed data:', data);
            return data;
            
        } catch (error) {
            console.error('=== API Error ===');
            console.error('Error details:', error);
            throw error;
        }
    }
};
