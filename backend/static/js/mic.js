// Shared microphone recognizer (client-side Web Speech API)
(function(){
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;

    const Microphone = {
        recognition: null,
        listening: false,
        lang: 'en-US',
        init() {
            // Attach to any mic buttons present on the page
            document.querySelectorAll('.mic-btn, #micBtn').forEach(btn => {
                try { btn.addEventListener('click', (e) => this.toggle(btn)); } catch(e){}
            });
        },
        toggle(btn) {
            if (!SpeechRecognition) return; // not supported
            if (this.listening) this.stop(btn);
            else this.start(btn);
        },
        start(btn) {
            if (!SpeechRecognition) return;
            if (this.listening) return;
            try {
                const recognition = new SpeechRecognition();
                recognition.lang = this.lang;
                recognition.interimResults = true;
                recognition.maxAlternatives = 1;

                const input = this._findInputForButton(btn);

                recognition.onresult = (event) => {
                    let interim = '';
                    let final = '';
                    for (let i = event.resultIndex; i < event.results.length; ++i) {
                        const res = event.results[i];
                        if (res.isFinal) final += res[0].transcript;
                        else interim += res[0].transcript;
                    }
                    if (input) input.value = (final + ' ' + interim).trim();
                };

                recognition.onerror = (ev) => {
                    console.warn('Speech recognition error', ev);
                    this.stop(btn);
                };

                recognition.onend = () => {
                    this.stop(btn);
                };

                recognition.start();
                this.recognition = recognition;
                this.listening = true;
                btn.classList.add('listening');
            } catch (e) {
                console.warn('Could not start speech recognition', e);
            }
        },
        stop(btn) {
            try {
                if (this.recognition) this.recognition.stop();
            } catch(e){}
            this.recognition = null;
            this.listening = false;
            if (btn) btn.classList.remove('listening');
        },
        _findInputForButton(btn) {
            // Look for a data-target attribute
            try {
                const target = btn.getAttribute && btn.getAttribute('data-target');
                if (target) return document.querySelector(target);
            } catch(e){}
            // Look for nearest input in DOM (sibling or within container)
            let el = btn.closest('.input-wrapper') || btn.closest('.input-area-container') || document;
            const input = el.querySelector('input[type="text"], input[type="search"], textarea');
            if (input) return input;
            // Fallback to common IDs
            return document.getElementById('messageInput') || document.getElementById('prompt');
        }
    };

    // Expose globally
    window.Microphone = Microphone;

    // Auto-init on DOM ready
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', () => Microphone.init());
    else Microphone.init();

})();
