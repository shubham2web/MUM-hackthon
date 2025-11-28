// Chat Module
const Chat = {
    currentMode: 'analytical',
    isProcessing: false,
    initialized: false, // Add flag to prevent duplicate initialization

    init() {
        if (this.initialized) return; // Prevent multiple initialization

        Messages.init('#chatMessages');
        this.setupEventListeners();

        // Check URL parameters first
        const urlParams = new URLSearchParams(window.location.search);
        const modeParam = urlParams.get('mode');

        // Also check sessionStorage for chatMode (from homepage)
        const storedMode = sessionStorage.getItem('chatMode');

        if (modeParam === 'debate' || storedMode === 'debate') {
            this.currentMode = 'debate';
        } else if (storedMode === 'simplified') {
            this.currentMode = 'simplified';
        } else {
            this.currentMode = 'analytical';
        }

        // Clear the stored mode after using
        sessionStorage.removeItem('chatMode');

        // Update page title based on mode
        const chatTitle = document.getElementById('chatTitle');
        if (chatTitle) {
            if (this.currentMode === 'debate') {
                chatTitle.textContent = '🎭 Atlas Debate Mode';
                chatTitle.classList.add('mode-debate');
                chatTitle.classList.remove('mode-chat');
            } else {
                chatTitle.textContent = '💬 Chat with Atlas';
                chatTitle.classList.add('mode-chat');
                chatTitle.classList.remove('mode-debate');
            }
        }

        // Restore per-mode chat if present, otherwise clear messages and add welcome
        const messages = document.getElementById('chatMessages');
        try {
            const mappedId = (typeof ChatStore !== 'undefined' && ChatStore.currentChatIdByMode) ? ChatStore.currentChatIdByMode[this.currentMode] : null;
            if (mappedId) {
                // Attempt to open the mapped chat for this mode
                try { ChatStore.openChat(mappedId); ChatStore.currentChatId = mappedId; }
                catch (e) { console.warn('Failed to open mapped chat', e); if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); } }
            } else {
                if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); }
            }
        } catch (e) {
            if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); }
        }

        // Check for OCR result from sessionStorage (old single file format)
        const ocrResult = sessionStorage.getItem('ocrResult');
        if (ocrResult) {
            this.handleOCRResult(JSON.parse(ocrResult));
            sessionStorage.removeItem('ocrResult'); // Clear after using
        }

        // Check for OCR results from homepage (new multiple files format)
        const ocrResults = sessionStorage.getItem('ocrResults');
        if (ocrResults) {
            this.handleMultipleOCRResults(JSON.parse(ocrResults));
            sessionStorage.removeItem('ocrResults'); // Clear after using
        }

        // If homepage set an initial prompt (text or link), auto-fill and send it
        const initialPrompt = sessionStorage.getItem('initialPrompt');
        if (initialPrompt) {
            try {
                const inputEl = document.getElementById('messageInput');
                if (inputEl) {
                    inputEl.value = initialPrompt;
                    // remove so it doesn't resend on reload
                    sessionStorage.removeItem('initialPrompt');
                    // Give the UI a moment to settle then send
                    setTimeout(() => { try { this.handleSend(); } catch (e) { console.warn('Auto send failed', e); } }, 250);
                }
            } catch (e) { console.warn('initialPrompt handling error', e); }
        }

        // Update navigation active state
        document.querySelectorAll('.nav-item').forEach(nav => {
            const navMode = nav.getAttribute('data-mode');
            // Match debate mode, or match chat for analytical/simplified modes
            if (navMode === 'debate' && this.currentMode === 'debate') {
                nav.classList.add('active');
            } else if (navMode === 'chat' && this.currentMode !== 'debate') {
                nav.classList.add('active');
            } else {
                nav.classList.remove('active');
            }
        });

        this.initialized = true; // Mark as initialized
    },

    handleOCRResult(ocrData) {
        // Clear welcome message
        const messages = document.getElementById('chatMessages');
        if (messages) {
            messages.innerHTML = '';
        }

        // Add user message showing the image was uploaded
        Messages.addUserMessage(`📷 Uploaded image: ${ocrData.filename}`);

        // Add AI analysis if available
        if (ocrData.aiAnalysis) {
            setTimeout(() => {
                Messages.addAIMessage(ocrData.aiAnalysis);
            }, 500);
        }
    },

    async handleMultipleOCRResults(ocrResults) {
        // Clear welcome message
        const messages = document.getElementById('chatMessages');
        if (messages) {
            messages.innerHTML = '';
        }

        // Add user message showing files were uploaded
        const fileNames = ocrResults.map(r => r.filename).join(', ');
        Messages.addUserMessage(`📷 Uploaded ${ocrResults.length} image(s): ${fileNames}`);

        // Optionally, you could ask the AI to analyze all the extracted text together
        const allText = ocrResults.map(r => `From ${r.filename}: ${r.extractedText}`).join('\n\n');
        const initialPrompt = sessionStorage.getItem('initialPrompt');

        // Ensure we have an active chat to persist messages
        try {
            if (!ChatStore.currentChatId) {
                const titleCandidate = initialPrompt || (ocrResults[0] && ocrResults[0].filename) || 'New Chat';
                const title = (titleCandidate && titleCandidate.length > 40) ? titleCandidate.slice(0, 40) + '...' : titleCandidate;
                const created = await ChatStore.createChat(title);
                if (created && (created._id || created.id)) ChatStore.currentChatId = created._id || created.id;
            }
        } catch (e) { console.warn('Could not create chat for OCR results', e); }

        if (initialPrompt) {
            setTimeout(async () => {
                Messages.showLoading('Analyzing uploaded images with evidence gathering...');
                try {
                    // Process each image with scraper-enhanced analysis
                    for (let i = 0; i < ocrResults.length; i++) {
                        const ocrData = ocrResults[i];

                        // Create FormData for re-processing with scraper
                        // We'll use the extracted text to trigger scraper analysis
                        const analysisPrompt = `${initialPrompt}\n\nAnalyze this text extracted from ${ocrData.filename}:\n\n${ocrData.extractedText}`;

                        // Add user message for this uploaded file and persist it
                        try {
                            const userText = `Uploaded ${ocrData.filename}: ${ocrData.extractedText || ''}`;
                            Messages.addUserMessage(`📷 ${ocrData.filename}`);
                            if (ChatStore.currentChatId) await ChatStore.appendMessage(ChatStore.currentChatId, 'user', userText);
                        } catch (e) { console.warn('append user ocr failed before analysis', e); }

                        const response = await fetch('/chat', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-API-Key': API_KEY
                            },
                            body: JSON.stringify({
                                message: analysisPrompt,
                                mode: this.currentMode,
                                use_scraper: true  // Enable scraper for fact-checking
                            })
                        });

                        const data = await response.json();

                        if (i === 0) {
                            Messages.hideLoading();
                        }

                        if (data.analysis || data.result || data.answer) {
                            const aiMessage = data.analysis || data.result || data.answer;
                            const displayMsg = `**Analysis of "${ocrData.filename}" (${i + 1}/${ocrResults.length}):**\n\n${aiMessage}`;
                            Messages.addAIMessage(displayMsg);
                            // Persist assistant reply to chat store (best-effort)
                            try { if (ChatStore.currentChatId) await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', aiMessage); } catch (e) { console.warn('append assistant message failed', e); }
                        }


                        // Small delay between processing multiple files
                        if (i < ocrResults.length - 1) {
                            await new Promise(resolve => setTimeout(resolve, 1000));
                        }
                    }
                } catch (error) {
                    Messages.hideLoading();
                    Messages.addAIMessage('❌ Error analyzing images: ' + error.message);
                }
            }, ocrResults.length * 300 + 500);
        }
    },

    switchMode(mode) {
        this.currentMode = mode;

        const chatTitle = document.getElementById('chatTitle');
        if (chatTitle) {
            if (mode === 'debate') {
                chatTitle.textContent = '🎭 Atlas Debate Mode';
                chatTitle.classList.add('mode-debate');
                chatTitle.classList.remove('mode-chat');
            } else {
                chatTitle.textContent = '💬 Chat with Atlas';
                chatTitle.classList.add('mode-chat');
                chatTitle.classList.remove('mode-debate');
            }
        }

        // Update URL without reloading
        const url = new URL(window.location);
        if (mode === 'debate') {
            url.searchParams.set('mode', 'debate');
        } else {
            url.searchParams.delete('mode');
        }
        window.history.pushState({}, '', url);

        // Try to restore the chat for the selected mode; fallback to welcome
        const messages = document.getElementById('chatMessages');
        try {
            const mappedId = (typeof ChatStore !== 'undefined' && ChatStore.currentChatIdByMode) ? ChatStore.currentChatIdByMode[mode] : null;
            if (mappedId) {
                try { ChatStore.openChat(mappedId); ChatStore.currentChatId = mappedId; }
                catch (e) { console.warn('Failed to open chat for mode', e); if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); } }
            } else {
                if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); }
            }
        } catch (e) {
            if (messages) { messages.innerHTML = ''; this.addWelcomeMessage(); }
        }

        console.log(`✅ Switched to ${mode} mode`);
    },

    setupEventListeners() {
        const sendBtn = document.getElementById('sendBtn');
        const input = document.getElementById('messageInput');

        sendBtn?.addEventListener('click', () => this.handleSend());
        input?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.handleSend();
            }
        });

        // Wire microphone: prefer browser Web Speech API when available (no server keys required)
        const micBtn = document.getElementById('micBtn');
        if (micBtn) {
            micBtn.addEventListener('click', async (ev) => {
                ev.preventDefault();

                // If browser supports Web Speech API, use it for client-only recognition (no server/API key needed)
                const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
                if (SpeechRecognition) {
                    try {
                        // Toggle recognition on/off if already listening
                        if (this._recognition && this._recognitionListening) {
                            this.stopWebSpeechRecognition();
                            return;
                        }
                        await this.startWebSpeechRecognition(SpeechRecognition);
                        return;
                    } catch (err) {
                        console.warn('Web Speech API failed, falling back to MediaRecorder', err);
                        // fallthrough to MediaRecorder fallback
                    }
                }

                // Fallback: MediaRecorder flow (server-side transcription)
                if (!this.recordingModal) this.createRecordingModal();
                this.showRecordingModal();
                try {
                    await this.startMediaRecording();
                } catch (err) {
                    console.error('Failed to start recording', err);
                    this.hideRecordingModal();
                    // Use a more helpful permission-aware handler
                    try { this.handleMediaPermissionError(err); } catch (e) { alert('Could not start microphone recording: ' + (err && err.message ? err.message : err)); }
                }
            });
        }
    },

    /************************************************************************
     * Recording UI + MediaRecorder
     ************************************************************************/
    createRecordingModal() {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay recording-modal';
        modal.innerHTML = `
            <div class="modal-content" role="dialog" aria-label="Recording">
                <h2 id="recordingTitle">Recording...</h2>
                <div id="recordingAnimation" style="margin:18px 0;"></div>
                <div style="display:flex; gap:10px; justify-content:center; margin-top:8px;">
                    <button id="stopRecordingBtn" class="input-btn">Stop</button>
                    <button id="cancelRecordingBtn" class="input-btn">Cancel</button>
                </div>
                <div id="recordingStatus" style="margin-top:12px; font-size:13px; color: #cbd5e1;">Listening...</div>
            </div>`;

        document.body.appendChild(modal);
        this.recordingModal = modal;

        // Simple animation: pulsing dot
        const anim = modal.querySelector('#recordingAnimation');
        anim.innerHTML = `<div class="rec-dot" style="width:18px;height:18px;border-radius:50%;background:#ff4d4d;margin:0 auto;box-shadow:0 0 12px rgba(255,77,77,0.6);"></div>`;

        modal.querySelector('#stopRecordingBtn').addEventListener('click', () => this.stopMediaRecording());
        modal.querySelector('#cancelRecordingBtn').addEventListener('click', () => {
            this.cancelRecording = true;
            this.stopMediaRecording();
        });
    },

    showRecordingModal() {
        if (!this.recordingModal) this.createRecordingModal();
        this.recordingModal.classList.add('active');
    },

    hideRecordingModal() {
        if (this.recordingModal) this.recordingModal.classList.remove('active');
    },

    /************************************************************************
     * Permission help modal + helpers
     ************************************************************************/
    handleMediaPermissionError(err) {
        // Normalize name
        const name = (err && err.name) ? err.name : null;

        if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
            // Show helpful modal guiding the user to enable microphone access
            this.showPermissionModal({
                title: 'Microphone access blocked',
                message: 'Microphone access was blocked by your browser or operating system. To record audio, please allow microphone access for this site and reload the page.',
                details: err && err.message ? err.message : 'Permission denied',
                reason: 'denied'
            });
            return;
        }

        if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
            this.showPermissionModal({
                title: 'No microphone detected',
                message: 'No microphone device was found. Please connect a microphone and ensure it is enabled in your OS settings.',
                details: err && err.message ? err.message : 'No microphone',
                reason: 'notfound'
            });
            return;
        }

        // Generic fallback: attempt to query permission state for more info
        this.checkMicrophonePermission().then(state => {
            if (state === 'denied') {
                this.showPermissionModal({
                    title: 'Microphone access blocked',
                    message: 'Your browser is blocking microphone access for this site. Please allow microphone access in Site Settings and reload.',
                    details: err && err.message ? err.message : 'Permission denied',
                    reason: 'denied'
                });
            } else if (state === 'prompt') {
                this.showPermissionModal({
                    title: 'Allow microphone access',
                    message: 'The browser may prompt you to allow microphone access. Please allow it and try again.',
                    details: err && err.message ? err.message : 'Permission prompt',
                    reason: 'prompt'
                });
            } else {
                // Unknown / other error
                this.showPermissionModal({
                    title: 'Could not start recording',
                    message: 'An unexpected error occurred while trying to start the microphone.',
                    details: (err && err.message) ? err.message : String(err),
                    reason: 'unknown'
                });
            }
        }).catch(() => {
            // If permissions API unavailable, show generic modal
            this.showPermissionModal({
                title: 'Microphone not available',
                message: 'Could not access the microphone. Check your browser and OS microphone permissions.',
                details: err && err.message ? err.message : 'Error',
                reason: 'unknown'
            });
        });
    },

    createPermissionModal() {
        if (this.permissionModal) return;
        const modal = document.createElement('div');
        modal.className = 'modal-overlay permission-modal';
        modal.innerHTML = `
            <div class="modal-content" role="dialog" aria-label="Microphone help">
                <h2 id="permissionTitle">Microphone access</h2>
                <div id="permissionMessage" style="margin:8px 0; color:#cbd5e1;"></div>
                <pre id="permissionDetails" style="white-space:pre-wrap; font-size:12px; color:#94a3b8; background:transparent; border:none;"></pre>
                <div style="display:flex; gap:8px; justify-content:center; margin-top:12px;">
                    <button id="permissionRetryBtn" class="input-btn">Retry</button>
                    <button id="permissionOpenSettingsBtn" class="input-btn">Open site settings</button>
                    <button id="permissionDiagBtn" class="input-btn">Diagnostics</button>
                    <button id="permissionCloseBtn" class="input-btn">Close</button>
                </div>
                <div style="margin-top:10px; font-size:13px; color:#9ca3af; text-align:left;">Tips:
                    <ul style="margin:6px 0 0 18px; padding:0; color:#9ca3af;">
                        <li>Reload the page after changing permissions.</li>
                        <li>Test in Incognito / Private mode to rule out extensions.</li>
                        <li>Check Windows Settings → Privacy → Microphone and allow apps to access it.</li>
                    </ul>
                </div>
            </div>`;

        document.body.appendChild(modal);
        this.permissionModal = modal;

        modal.querySelector('#permissionCloseBtn').addEventListener('click', () => this.hidePermissionModal());
        modal.querySelector('#permissionRetryBtn').addEventListener('click', async () => {
            this.hidePermissionModal();
            // Try to start recording again
            try { await this.startMediaRecording(); } catch (e) { this.handleMediaPermissionError(e); }
        });

        modal.querySelector('#permissionOpenSettingsBtn').addEventListener('click', () => {
            // Try to guide user to site settings; best-effort to open a helpful URL
            try {
                // Many browsers block chrome:// links; open WebRTC sample as alternative
                window.open('chrome://settings/content/microphone', '_blank');
            } catch (e) {
                try { window.open('about:preferences#privacy', '_blank'); } catch (e) { /* ignore */ }
            }
            // Also open a troubleshooting sample page
            window.open('https://webrtc.github.io/samples/src/content/getusermedia/', '_blank');
        });

        // Diagnostics: show enumerateDevices + permissions info
        modal.querySelector('#permissionDiagBtn').addEventListener('click', async () => {
            const detailsEl = modal.querySelector('#permissionDetails');
            detailsEl.textContent = 'Running diagnostics...';
            try {
                const perm = navigator.permissions && navigator.permissions.query ? await navigator.permissions.query({ name: 'microphone' }) : null;
                const permState = perm ? perm.state : 'unavailable';
                let devices = [];
                try { devices = await navigator.mediaDevices.enumerateDevices(); } catch (e) { devices = [{ error: String(e) }]; }

                const out = {
                    permissionState: permState,
                    userAgent: navigator.userAgent,
                    devices: devices.map(d => ({ kind: d.kind, label: d.label, deviceId: d.deviceId }))
                };
                detailsEl.textContent = JSON.stringify(out, null, 2);
            } catch (e) {
                detailsEl.textContent = 'Diagnostics failed: ' + (e && e.message ? e.message : String(e));
            }
        });
    },

    showPermissionModal({ title, message, details, reason } = {}) {
        if (!this.permissionModal) this.createPermissionModal();
        const modal = this.permissionModal;
        modal.querySelector('#permissionTitle').textContent = title || 'Microphone access';
        modal.querySelector('#permissionMessage').textContent = message || '';
        modal.querySelector('#permissionDetails').textContent = details || '';
        modal.classList.add('active');
        // Update a simple status from Permissions API
        this.checkMicrophonePermission().then(state => {
            const statusEl = modal.querySelector('#permissionMessage');
            if (state === 'denied') statusEl.textContent += ' (permission state: denied)';
            else if (state === 'granted') statusEl.textContent += ' (permission state: granted)';
            else if (state === 'prompt') statusEl.textContent += ' (permission state: prompt)';
        }).catch(() => {});
    },

    hidePermissionModal() {
        if (this.permissionModal) this.permissionModal.classList.remove('active');
    },

    async checkMicrophonePermission() {
        if (!navigator.permissions || !navigator.permissions.query) return null;
        try {
            const p = await navigator.permissions.query({ name: 'microphone' });
            return p.state; // 'granted' | 'denied' | 'prompt'
        } catch (e) {
            return null;
        }
    },

    async startMediaRecording() {
        // Reset any previous state
        this.cancelRecording = false;
        this.recordedChunks = [];

        // Request microphone access
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this._mediaStream = stream;

        // Setup MediaRecorder
        const options = { mimeType: 'audio/webm' };
        try {
            this.mediaRecorder = new MediaRecorder(stream, options);
        } catch (e) {
            // Fallback to default
            this.mediaRecorder = new MediaRecorder(stream);
        }

        this.mediaRecorder.ondataavailable = (ev) => {
            if (ev.data && ev.data.size > 0) this.recordedChunks.push(ev.data);
        };

        this.mediaRecorder.onstop = async () => {
            // Stop audio nodes if any
            try { if (this._audioContext) { this._audioContext.close(); this._audioContext = null; } } catch (e) {}

            this.hideRecordingModal();

            if (this.cancelRecording) {
                this.recordedChunks = [];
                return;
            }

            const blob = new Blob(this.recordedChunks, { type: this.recordedChunks[0]?.type || 'audio/webm' });
            try {
                const transcript = await this.sendAudioToServer(blob);
                const input = document.getElementById('messageInput');
                if (input && transcript) input.value = transcript;
            } catch (err) {
                console.error('Transcription failed', err);
                alert('Transcription failed: ' + (err.message || err));
            }
        };

        // Start recording
        this.mediaRecorder.start();

        // Start VAD (silence detection) to auto-stop
        this.startVAD(stream);
    },

    /************************************************************************
     * Web Speech API (client-only) recognition fallback
     * Uses browser speech recognition (no server/API key) when available.
     ************************************************************************/
    async startWebSpeechRecognition(SpeechRecognitionCtor) {
        if (this._recognition && this._recognitionListening) return;

        // Create recognition instance
        const recognition = new SpeechRecognitionCtor();
        recognition.lang = 'en-US';
        recognition.interimResults = true;
        recognition.maxAlternatives = 1;

        this._recognition = recognition;
        this._recognitionListening = true;

        const input = document.getElementById('messageInput');
        let interimText = '';

        const micBtn = document.getElementById('micBtn');
        if (micBtn) micBtn.classList.add('listening');

        recognition.onresult = (event) => {
            let finalTranscript = '';
            interimText = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                const res = event.results[i];
                if (res.isFinal) finalTranscript += res[0].transcript;
                else interimText += res[0].transcript;
            }
            if (input) input.value = (finalTranscript + ' ' + interimText).trim();
        };

        recognition.onerror = (ev) => {
            console.error('Speech recognition error', ev);
            this._recognitionListening = false;
            if (micBtn) micBtn.classList.remove('listening');
        };

        recognition.onend = () => {
            this._recognitionListening = false;
            if (micBtn) micBtn.classList.remove('listening');
            // leave final value in input
        };

        recognition.start();
    },

    stopWebSpeechRecognition() {
        if (!this._recognition) return;
        try {
            this._recognition.stop();
        } catch (e) { console.warn('recognition.stop failed', e); }
        this._recognitionListening = false;
        const micBtn = document.getElementById('micBtn');
        if (micBtn) micBtn.classList.remove('listening');
    },

    stopMediaRecording() {
        try {
            if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') this.mediaRecorder.stop();
        } catch (e) { console.warn('mediaRecorder.stop error', e); }
        try { if (this._mediaStream) { this._mediaStream.getTracks().forEach(t => t.stop()); this._mediaStream = null; } } catch (e) {}
        try { if (this._vadInterval) { clearInterval(this._vadInterval); this._vadInterval = null; } } catch (e) {}
    },

    startVAD(stream) {
        // Very small VAD implementation using WebAudio RMS
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            this._audioContext = new AudioContext();
            const source = this._audioContext.createMediaStreamSource(stream);
            const analyser = this._audioContext.createAnalyser();
            analyser.fftSize = 2048;
            source.connect(analyser);

            const data = new Uint8Array(analyser.fftSize);
            const silenceThreshold = 6; // adjust (lower = more sensitive)
            let silentMs = 0;
            const checkInterval = 250; // ms

            this._vadInterval = setInterval(() => {
                analyser.getByteTimeDomainData(data);
                // compute RMS
                let sum = 0;
                for (let i = 0; i < data.length; i++) {
                    const v = (data[i] - 128) / 128;
                    sum += v * v;
                }
                const rms = Math.sqrt(sum / data.length);
                const db = 20 * Math.log10(rms + 1e-8);

                // Update UI status
                const statusEl = this.recordingModal ? this.recordingModal.querySelector('#recordingStatus') : null;
                if (statusEl) statusEl.textContent = `Listening... (level: ${Math.round(db)})`;

                if (rms < 0.01) {
                    silentMs += checkInterval;
                } else {
                    silentMs = 0;
                }

                // If silence for > 1400ms, stop automatically
                if (silentMs > 1400) {
                    this.stopMediaRecording();
                }
            }, checkInterval);
        } catch (e) {
            console.warn('VAD not available', e);
        }
    },

    async sendAudioToServer(blob) {
        const form = new FormData();
        form.append('audio', blob, 'recording.webm');

        // Include application API key header if available (server requires X-API-Key)
        const fetchOpts = {
            method: 'POST',
            body: form,
            headers: {}
        };
        try { if (typeof API_KEY !== 'undefined' && API_KEY) fetchOpts.headers['X-API-Key'] = API_KEY; } catch (e) {}

        const resp = await fetch('/transcribe', fetchOpts);

        if (!resp.ok) {
            // Try to parse server JSON for structured error
            const j = await resp.json().catch(() => null);
            if (resp.status === 401) {
                const serverMsg = (j && j.error) ? j.error : 'Unauthorized';
                throw new Error(`Unauthorized: ${serverMsg}. The server requires an application API key (X-API-Key) to use transcription.`);
            }
            throw new Error((j && j.error) ? j.error : `Server returned ${resp.status}`);
        }

        const data = await resp.json();
        if (data && data.success && data.transcript) return data.transcript;
        throw new Error('No transcript returned');
    },

    async handleSend() {
        const input = document.getElementById('messageInput');
        const message = input.value.trim();

        if (!message || this.isProcessing) return;

        this.isProcessing = true;
        input.value = '';
        // Ensure we have a chat to append to. Create one if necessary.
        try {
            if (!ChatStore.currentChatId) {
                const title = message.length > 40 ? message.slice(0, 40) + '...' : message;
                const created = await ChatStore.createChat(title || 'New Chat');
                if (created && (created._id || created.id)) {
                    ChatStore.currentChatId = created._id || created.id;
                    await ChatStore.listChats();
                }
            }
        } catch (e) { console.warn('Could not create/open chat before send', e); }

        Messages.addUserMessage(message);

        // Persist the user message to the chat store (best-effort)
        try { if (ChatStore.currentChatId) ChatStore.appendMessage(ChatStore.currentChatId, 'user', message); } catch (e) { console.warn('append user message failed', e); }

        // Process all attached files before sending message
        if (Attachments.attachedFiles && Attachments.attachedFiles.length > 0) {
            Messages.addAIMessage(`🔄 Processing ${Attachments.attachedFiles.length} attached file(s)...`);

            for (let i = 0; i < Attachments.attachedFiles.length; i++) {
                const file = Attachments.attachedFiles[i];
                const fileName = file.name.toLowerCase();

                // Add separator for multiple files
                if (Attachments.attachedFiles.length > 1) {
                    Messages.addAIMessage(`\n--- Processing file ${i + 1} of ${Attachments.attachedFiles.length}: ${file.name} ---\n`);
                }

                // Check if it's an image or text file
                const isImage = fileName.endsWith('.jpg') || fileName.endsWith('.jpeg') || fileName.endsWith('.png');
                const isTextFile = fileName.endsWith('.md') || fileName.endsWith('.txt');

                if (isImage) {
                    await Attachments.processImageWithOCR(file);
                } else if (isTextFile) {
                    await Attachments.processTextFile(file);
                }

                // Small delay between files
                if (i < Attachments.attachedFiles.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }

            // Clear attached files after processing
            Attachments.attachedFiles = [];
            Messages.addAIMessage(`✅ All files processed successfully!\n\n`);

            // Don't send additional message to chat endpoint - OCR already provided analysis
            this.isProcessing = false;
            return;
        }

        Messages.showLoading();

        // Check v2 toggle state early to set appropriate timeout
        const v2EnabledForTimeout = document.getElementById('v2Toggle')?.checked || false;
        
        // Add timeout for the request:
        // - v2.0 analysis: 300 seconds (5 minutes) - more complex with role reversal
        // - Standard: 180 seconds (3 minutes) for OCR + AI analysis
        const timeoutMs = v2EnabledForTimeout ? 300000 : 180000;
        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error('Request timed out')), timeoutMs)
        );

            try {
                // Check v2 toggle state
                const v2Enabled = document.getElementById('v2Toggle')?.checked || false;
                console.log('Sending message:', message, 'Mode:', this.currentMode, 'V2 enabled:', v2Enabled);
                
                // Collect conversation history from chat messages
                const conversationHistory = this.getConversationHistory();
                
                let response;
                
                // DEBATE MODE: Always use streaming debate, ignore v2 toggle
                if (this.currentMode === 'debate') {
                    console.log('🎭 Running debate mode...');
                    response = await Promise.race([
                        API.sendMessage(message, 'debate', conversationHistory),
                        timeoutPromise
                    ]);
                    
                    // DON'T hide loading yet - let it continue until first debate message arrives
                    
                    // Should be SSE stream
                    if (response && response.isStream) {
                        await this.handleDebateStream(response.response, message);
                    } else {
                        Messages.hideLoading();
                        Messages.addAIMessage('Error: Expected debate stream but got regular response.');
                    }
                }
                // CHAT MODE: Use v2.0 if enabled, otherwise standard chat
                else {
                    if (v2Enabled && typeof ATLASv2 !== 'undefined') {
                        console.log('💎 Using v2.0 enhanced analysis...');
                        // Use v2.0 enhanced analysis
                        response = await Promise.race([
                            ATLASv2.analyzeWithV2(message, {
                                num_agents: 4,
                                enable_reversal: true,
                                reversal_rounds: 1
                            }),
                            timeoutPromise
                        ]);
                        
                        console.log('Received v2.0 response:', response);
                        Messages.hideLoading();
                        
                        if (response.success && response.data) {
                            // Use V2UI to render enhanced response
                            const v2Card = V2UI.createV2ResponseCard(response.data);
                            this.addV2Card(v2Card);
                            // Persist a short synthesis from v2 response if available
                            try {
                                const synth = response.data.synthesis || response.data.summary || JSON.stringify(response.data || {});
                                if (ChatStore.currentChatId) ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', synth);
                            } catch (e) { console.warn('append v2 response failed', e); }
                        } else {
                            Messages.addAIMessage(response.error || 'v2.0 analysis failed. Please try again.');
                        }
                    } else {
                        console.log('💬 Using standard chat analysis...');
                        // Use standard v1.0 analysis
                        response = await Promise.race([
                            API.sendMessage(message, 'analytical', conversationHistory),
                            timeoutPromise
                        ]);
                        
                        console.log('Received response:', response);
                        Messages.hideLoading();
                        
                        // Regular chat response
                        const aiMessage = response.analysis || 
                                        response.result || 
                                        response.answer ||
                                        'No response received.';
                                        
                        Messages.addAIMessage(aiMessage);
                        // Persist assistant reply (best-effort)
                        try { if (ChatStore.currentChatId) ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', aiMessage); } catch (e) { console.warn('append assistant message failed', e); }
                    }
                }
                
            } catch (error) {
                Messages.hideLoading();
                
                if (error.message === 'Request timed out') {
                    const v2On = document.getElementById('v2Toggle')?.checked || false;
                    if (v2On) {
                        Messages.addAIMessage('⏱️ The v2.0 enhanced analysis took too long (API rate limits may have caused delays). Try disabling v2.0 for faster results, or try again in a minute.');
                    } else {
                        Messages.addAIMessage('⏱️ The request took too long. Please try a simpler question.');
                    }
                } else {
                    Messages.addAIMessage('❌ Error: ' + error.message);
                }
                
                console.error('Chat error:', error);
            } finally {
                this.isProcessing = false;
            }
        },

    async handleDebateStream(response, originalTopic) {
        console.log('📡 Handling debate stream...');
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let currentRole = null;
        let currentContent = '';
        let messageDiv = null;
        let firstMessageReceived = false; // Track if we've received first message
        let allDebateContent = []; // Store all debate messages for persistence

        try {
            let currentEventType = null;  // Track current SSE event type
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                const lines = chunk.split('\n');

                for (const line of lines) {
                    if (!line.trim() || line.startsWith(':')) continue;

                    // Track event type from SSE
                    if (line.startsWith('event: ')) {
                        currentEventType = line.substring(7).trim();
                        console.log('📨 SSE Event:', currentEventType);
                        continue;
                    }

                    if (line.startsWith('data: ')) {
                        const data = line.substring(6).trim();

                        if (data === '[DONE]') {
                            // Flush any remaining content
                            if (currentContent && messageDiv) {
                                messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                allDebateContent.push({ role: currentRole, content: currentContent });
                            }

                            // Persist the complete debate to chat store
                            if (ChatStore.currentChatId && allDebateContent.length > 0) {
                                const debateTranscript = allDebateContent.map(d =>
                                    `**${d.role.toUpperCase()}**: ${d.content}`
                                ).join('\n\n');
                                try {
                                    await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', debateTranscript);
                                } catch (e) { console.warn('Failed to persist debate', e); }
                            }

                            console.log('✅ Debate stream complete');
                            currentEventType = null;
                            return;
                        }

                        try {
                            const json = JSON.parse(data);
                            
                            // 🎯 Handle FINAL VERDICT event
                            if (currentEventType === 'final_verdict' || json.verdict) {
                                console.log('⚖️ Final Verdict received:', json);
                                this.displayFinalVerdict(json);
                                currentEventType = null;
                                continue;
                            }
                            
                            // 📊 Handle analytics metrics event
                            if (currentEventType === 'analytics_metrics') {
                                console.log('📊 Analytics received:', json);
                                // Could display analytics summary here
                                currentEventType = null;
                                continue;
                            }
                            
                            // 🔄 Handle role reversal events
                            if (currentEventType === 'role_reversal_start') {
                                console.log('🔄 Role Reversal started');
                                this.displayRoleReversalNotice();
                                currentEventType = null;
                                continue;
                            }
                            
                            if (currentEventType === 'role_reversal_complete') {
                                console.log('🔄 Role Reversal complete:', json);
                                currentEventType = null;
                                continue;
                            }

                            // Handle "end" event - debate complete
                            if (json.message === "Debate complete." || currentEventType === 'end') {
                                // Ensure loading is hidden
                                Messages.hideLoading();

                                // Flush any remaining content
                                if (currentContent && messageDiv) {
                                    messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                    allDebateContent.push({ role: currentRole, content: currentContent });
                                }

                                // Persist the complete debate to chat store
                                if (ChatStore.currentChatId && allDebateContent.length > 0) {
                                    const debateTranscript = allDebateContent.map(d =>
                                        `**${d.role.toUpperCase()}**: ${d.content}`
                                    ).join('\n\n');
                                    try {
                                        await ChatStore.appendMessage(ChatStore.currentChatId, 'assistant', debateTranscript);
                                    } catch (e) { console.warn('Failed to persist debate', e); }
                                }

                                // Add completion message
                                const completionDiv = document.createElement('div');
                                completionDiv.className = 'message ai-message';
                                completionDiv.innerHTML = `
                                        <div style="text-align: center; padding: 20px; border: 2px solid #10b981; border-radius: 8px; background: rgba(16, 185, 129, 0.1);">
                                            <div style="font-size: 24px; margin-bottom: 10px;">✅</div>
                                            <div style="font-weight: 600; color: #10b981; margin-bottom: 5px;">Debate Complete</div>
                                            <div style="color: #6b7280; font-size: 14px;">The moderator has provided the final synthesis above.</div>
                                        </div>
                                    `;
                                Messages.container.appendChild(completionDiv);
                                Messages.container.scrollTop = Messages.container.scrollHeight;
                                console.log('✅ Debate completed successfully');
                                currentEventType = null;
                                return;
                            }

                            // Check for role change
                            if (json.role && json.role !== currentRole) {
                                // Hide loading indicator on first message
                                if (!firstMessageReceived) {
                                    console.log('🎯 First debate message received, hiding loading...');
                                    Messages.hideLoading();
                                    firstMessageReceived = true;
                                }

                                // Flush previous content
                                if (currentContent && messageDiv) {
                                    messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                    allDebateContent.push({ role: currentRole, content: currentContent });
                                }

                                // Start new message
                                currentRole = json.role;
                                currentContent = '';
                                messageDiv = this.createDebateMessage(currentRole);
                            }

                            // Append content (backend sends "text" not "content")
                            if (json.text || json.content) {
                                currentContent += (json.text || json.content);
                                if (messageDiv) {
                                    messageDiv.innerHTML = this.formatDebateContent(currentContent, currentRole);
                                }
                            }

                        } catch (e) {
                            console.error('Error parsing SSE data:', e, data);
                        }
                    }
                }
            }
        } catch (error) {
            console.error('Error in debate stream:', error);
            Messages.hideLoading(); // Hide loading on error
            Messages.addAIMessage('❌ Error streaming debate: ' + error.message);
        }
    },

    createDebateMessage(role) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        Messages.container.appendChild(messageDiv);
        Messages.container.scrollTop = Messages.container.scrollHeight;
        return messageDiv;
    },
    
    /**
     * Display the final verdict from the Chief Fact-Checker
     */
    displayFinalVerdict(verdictData) {
        const verdict = verdictData.verdict || 'COMPLEX';
        const confidence = verdictData.confidence || 50;
        const reasoning = verdictData.reasoning || 'Analysis complete.';
        const keyEvidence = verdictData.key_evidence || [];
        const winningArg = verdictData.winning_argument || '';
        
        // Determine verdict styling
        let verdictColor, verdictIcon, verdictBg;
        switch(verdict.toUpperCase()) {
            case 'VERIFIED':
                verdictColor = '#10b981';
                verdictIcon = '✅';
                verdictBg = 'rgba(16, 185, 129, 0.1)';
                break;
            case 'DEBUNKED':
                verdictColor = '#ef4444';
                verdictIcon = '❌';
                verdictBg = 'rgba(239, 68, 68, 0.1)';
                break;
            case 'COMPLEX':
            default:
                verdictColor = '#f59e0b';
                verdictIcon = '⚖️';
                verdictBg = 'rgba(245, 158, 11, 0.1)';
        }
        
        // Build key evidence HTML
        let evidenceHtml = '';
        if (keyEvidence.length > 0) {
            evidenceHtml = `
                <div style="margin-top: 15px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                    <div style="font-weight: 600; margin-bottom: 8px; color: #9ca3af;">📋 Key Evidence:</div>
                    <ul style="margin: 0; padding-left: 20px; color: #d1d5db;">
                        ${keyEvidence.map(e => `<li style="margin-bottom: 4px;">${e}</li>`).join('')}
                    </ul>
                </div>
            `;
        }
        
        // Build winning argument HTML
        let winningArgHtml = '';
        if (winningArg) {
            winningArgHtml = `
                <div style="margin-top: 12px; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 6px;">
                    <div style="font-weight: 600; color: #9ca3af; margin-bottom: 4px;">🏆 Strongest Argument:</div>
                    <div style="color: #e5e7eb; font-style: italic;">"${winningArg}"</div>
                </div>
            `;
        }
        
        const verdictDiv = document.createElement('div');
        verdictDiv.className = 'message ai-message';
        verdictDiv.innerHTML = `
            <div style="padding: 20px; border: 2px solid ${verdictColor}; border-radius: 12px; background: ${verdictBg};">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 15px;">
                    <span style="font-size: 32px;">${verdictIcon}</span>
                    <div>
                        <div style="font-size: 12px; text-transform: uppercase; color: #9ca3af; letter-spacing: 1px;">Final Verdict</div>
                        <div style="font-size: 24px; font-weight: 700; color: ${verdictColor};">${verdict}</div>
                    </div>
                    <div style="margin-left: auto; text-align: right;">
                        <div style="font-size: 11px; color: #9ca3af;">Confidence</div>
                        <div style="font-size: 20px; font-weight: 600; color: ${verdictColor};">${confidence}%</div>
                    </div>
                </div>
                
                <div style="color: #e5e7eb; line-height: 1.6;">
                    ${reasoning}
                </div>
                
                ${winningArgHtml}
                ${evidenceHtml}
                
                <div style="margin-top: 15px; font-size: 11px; color: #6b7280; text-align: center;">
                    ⚖️ Verdict by Chief Fact-Checker AI
                </div>
            </div>
        `;
        
        Messages.container.appendChild(verdictDiv);
        Messages.container.scrollTop = Messages.container.scrollHeight;
    },
    
    /**
     * Display notice when role reversal round starts
     */
    displayRoleReversalNotice() {
        const noticeDiv = document.createElement('div');
        noticeDiv.className = 'message ai-message';
        noticeDiv.innerHTML = `
            <div style="text-align: center; padding: 15px; border: 1px dashed #8b5cf6; border-radius: 8px; background: rgba(139, 92, 246, 0.1);">
                <div style="font-size: 20px; margin-bottom: 8px;">🔄</div>
                <div style="font-weight: 600; color: #8b5cf6;">Role Reversal Round</div>
                <div style="color: #9ca3af; font-size: 13px; margin-top: 4px;">
                    Debaters are now switching positions to stress-test their arguments
                </div>
            </div>
        `;
        Messages.container.appendChild(noticeDiv);
        Messages.container.scrollTop = Messages.container.scrollHeight;
    },

    formatDebateContent(content, role) {
        let icon, label, colorClass;

        if (role === 'proponent') {
            icon = '🔵';
            label = 'PROPONENT';
            colorClass = 'proponent';
        } else if (role === 'opponent') {
            icon = '🔴';
            label = 'OPPONENT';
            colorClass = 'opponent';
        } else if (role === 'moderator') {
            icon = '🎙️';
            label = 'MODERATOR';
            colorClass = 'moderator';
        } else {
            icon = '💬';
            label = role.toUpperCase();
            colorClass = 'default';
        }

        return `
                <div class="debate-message ${colorClass}">
                    <div class="debate-header">
                        <span class="debate-icon">${icon}</span>
                        <strong>${label}</strong>
                    </div>
                    <div class="debate-content">${this.markdownToHtml(content)}</div>
                </div>
            `;
    },

    markdownToHtml(text) {
        // Basic markdown conversion
        return text
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>');
    },

    addWelcomeMessage() {
        let message;
        if (this.currentMode === 'debate') {
            message = "🎭 **Welcome to Debate Mode!**\n\nI'll analyze your topic by presenting arguments from both sides:\n• 🔵 **Proponent** - Arguments in favor\n• 🔴 **Opponent** - Counter-arguments\n• 🎙️ **Moderator** - Synthesis and balance\n\nAsk me to debate any topic!";
        } else {
            message = "👋 Hello! I'm **Atlas**, your misinformation fighter.\n\n💬 **Chat Mode**: I'll provide clear, factual analysis of your questions.\n\n💡 **Tip**: Toggle v2.0 for enhanced multi-perspective analysis, or switch to Debate mode for structured debates!";
        }
        Messages.addAIMessage(message);
    },

    addV2Card(cardElement) {
        // Add v2.0 response card to messages
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message ai-message';
        messageDiv.style.background = 'transparent';
        messageDiv.appendChild(cardElement);
        Messages.container.appendChild(messageDiv);
        Messages.scrollToBottom();
    },

    getConversationHistory() {
        // Collect all user and AI messages from the chat for context
        const history = [];
        const messagesContainer = document.getElementById('chatMessages');
        if (!messagesContainer) return history;

        const messageElements = messagesContainer.querySelectorAll('.message');
        messageElements.forEach(msgEl => {
            const isUser = msgEl.classList.contains('user-message');
            const messageTextEl = msgEl.querySelector('.message-text');

            if (messageTextEl) {
                const text = messageTextEl.textContent.trim();
                // Skip empty messages, loading indicators, and system messages
                if (text && !msgEl.classList.contains('loading-message') && text.length > 0) {
                    history.push({
                        role: isUser ? 'user' : 'assistant',
                        content: text
                    });
                }
            }
        });

        // Limit history to last 10 messages to avoid token limits
        return history.slice(-10);
    }
};
