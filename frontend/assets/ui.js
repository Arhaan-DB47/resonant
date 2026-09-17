/**
 * ui.js -- Main UI Controller
 *
 * Wires everything together: loads personas, handles recording,
 * sends audio to the API, and displays responses in the chat.
 *
 * This is the last script loaded, so API, Recorder, and Player
 * are all available when this runs.
 */

const UI = {
    // State
    personas: [],
    selectedPersonaId: null,
    isProcessing: false,

    // DOM references (cached on init)
    dom: {},

    /**
     * Initialize the UI — called on page load.
     */
    async init() {
        // Cache DOM elements
        this.dom = {
            personaSelect: document.getElementById('persona-select'),
            languageSelect: document.getElementById('language-select'),
            personaName: document.getElementById('persona-name'),
            personaRole: document.getElementById('persona-role'),
            personaInstitution: document.getElementById('persona-institution'),
            personaAvatar: document.getElementById('persona-avatar'),
            recordBtn: document.getElementById('record-btn'),
            recordHint: document.getElementById('record-hint'),
            recordingIndicator: document.getElementById('recording-indicator'),
            chatMessages: document.getElementById('chat-messages'),
            chatEmpty: document.getElementById('chat-empty'),
            clearChatBtn: document.getElementById('clear-chat-btn'),
            loadingOverlay: document.getElementById('loading-overlay'),
            loadingText: document.getElementById('loading-text'),
            statusDot: document.getElementById('status-indicator'),
            statusText: document.getElementById('status-text'),
            // Create Persona Modal
            createPersonaBtn: document.getElementById('create-persona-btn'),
            createModal: document.getElementById('create-persona-modal'),
            createForm: document.getElementById('create-persona-form'),
            modalCloseBtn: document.getElementById('modal-close-btn'),
            modalCancelBtn: document.getElementById('modal-cancel-btn'),
        };

        // Bind events
        this.dom.personaSelect.addEventListener('change', () => this.onPersonaChange());
        this.dom.clearChatBtn.addEventListener('click', () => this.clearChat());

        // Create Persona modal events
        this.dom.createPersonaBtn.addEventListener('click', () => this.openCreateModal());
        this.dom.modalCloseBtn.addEventListener('click', () => this.closeCreateModal());
        this.dom.modalCancelBtn.addEventListener('click', () => this.closeCreateModal());
        this.dom.createModal.addEventListener('click', (e) => {
            if (e.target === this.dom.createModal) this.closeCreateModal();
        });
        this.dom.createForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.submitCreatePersona();
        });

        // Record button: mousedown/mouseup for hold-to-record
        this.dom.recordBtn.addEventListener('mousedown', (e) => { e.preventDefault(); this.startRecording(); });
        this.dom.recordBtn.addEventListener('mouseup', () => this.stopRecording());
        this.dom.recordBtn.addEventListener('mouseleave', () => { if (Recorder.isRecording) this.stopRecording(); });

        // Touch support for mobile
        this.dom.recordBtn.addEventListener('touchstart', (e) => { e.preventDefault(); this.startRecording(); });
        this.dom.recordBtn.addEventListener('touchend', (e) => { e.preventDefault(); this.stopRecording(); });

        // Load data
        await this.checkHealth();
        await this.loadPersonas();

        console.log('[UI] Initialized');
    },

    /**
     * Check server health and update status indicator.
     */
    async checkHealth() {
        try {
            const health = await API.healthCheck();

            if (health.status === 'healthy') {
                this.dom.statusDot.className = 'status-dot online';
                this.dom.statusText.textContent = 'All systems online';
            } else if (health.status === 'degraded') {
                this.dom.statusDot.className = 'status-dot degraded';
                this.dom.statusText.textContent = 'LLM offline (fallback mode)';
            } else {
                this.dom.statusDot.className = 'status-dot offline';
                this.dom.statusText.textContent = 'Server issues';
            }
        } catch (err) {
            this.dom.statusDot.className = 'status-dot offline';
            this.dom.statusText.textContent = 'Server unreachable';
            this.showToast('Cannot connect to server. Is it running?', 'error');
        }
    },

    /**
     * Load personas from the API and populate the dropdown.
     */
    async loadPersonas() {
        try {
            this.personas = await API.getPersonas();

            this.dom.personaSelect.innerHTML = '';

            if (this.personas.length === 0) {
                this.dom.personaSelect.innerHTML = '<option value="">No personas found</option>';
                this.showToast('No personas found. Create one via /docs first.', 'info');
                return;
            }

            // Add a placeholder option
            const placeholder = document.createElement('option');
            placeholder.value = '';
            placeholder.textContent = `Select a persona (${this.personas.length} available)`;
            this.dom.personaSelect.appendChild(placeholder);

            // Add each persona
            for (const p of this.personas) {
                const opt = document.createElement('option');
                opt.value = p.id;
                opt.textContent = `${p.name} — ${p.role || 'No role'}`;
                this.dom.personaSelect.appendChild(opt);
            }

            // Auto-select first persona if only one exists
            if (this.personas.length === 1) {
                this.dom.personaSelect.value = this.personas[0].id;
                this.onPersonaChange();
            }
        } catch (err) {
            console.error('[UI] Failed to load personas:', err);
            this.dom.personaSelect.innerHTML = '<option value="">Failed to load</option>';
            this.showToast('Failed to load personas', 'error');
        }
    },

    /**
     * Handle persona selection change.
     */
    async onPersonaChange() {
        const id = parseInt(this.dom.personaSelect.value);

        if (!id) {
            this.selectedPersonaId = null;
            this.dom.personaName.textContent = 'Select a Persona';
            this.dom.personaRole.textContent = 'Choose a digital twin to talk to';
            this.dom.personaInstitution.textContent = '';
            this.dom.personaAvatar.textContent = '?';
            this.dom.recordBtn.disabled = true;
            this.dom.recordHint.textContent = 'Select a persona to start';
            return;
        }

        this.selectedPersonaId = id;

        // Find the persona in our cached list
        const persona = this.personas.find(p => p.id === id);
        if (persona) {
            this.dom.personaName.textContent = persona.name || 'Unknown';
            this.dom.personaRole.textContent = persona.role || '';
            this.dom.personaInstitution.textContent = persona.institution || '';
            this.dom.personaAvatar.textContent = (persona.name || '?')[0].toUpperCase();
        }

        // Enable recording
        this.dom.recordBtn.disabled = false;
        this.dom.recordHint.textContent = 'Hold to record your question';

        // Initialize recorder if not done yet
        if (!Recorder.stream) {
            const granted = await Recorder.init();
            if (!granted) {
                this.dom.recordBtn.disabled = true;
                this.dom.recordHint.textContent = 'Microphone access denied';
                this.showToast('Microphone permission is required to record audio', 'error');
            }
        }
    },

    /**
     * Start recording audio.
     */
    startRecording() {
        if (!this.selectedPersonaId || this.isProcessing) return;
        if (!Recorder.stream) return;

        Recorder.start();
        this.dom.recordBtn.classList.add('recording');
        this.dom.recordingIndicator.classList.add('visible');
        this.dom.recordHint.textContent = 'Release to send';
    },

    /**
     * Stop recording and send to the pipeline.
     */
    async stopRecording() {
        if (!Recorder.isRecording) return;

        this.dom.recordBtn.classList.remove('recording');
        this.dom.recordingIndicator.classList.remove('visible');
        this.dom.recordHint.textContent = 'Hold to record your question';

        const audioBlob = await Recorder.stop();
        if (!audioBlob || audioBlob.size < 1000) {
            this.showToast('Recording too short. Hold the button longer.', 'info');
            return;
        }

        // Send to the pipeline
        await this.processAudio(audioBlob);
    },

    /**
     * Send audio to the backend and display the response.
     */
    async processAudio(audioBlob) {
        if (this.isProcessing) return;
        this.isProcessing = true;

        const language = this.dom.languageSelect.value;
        const personaId = this.selectedPersonaId;

        // Show loading overlay with stage animations
        this.showLoading();

        try {
            // Animate through the stages
            this.setLoadingStage('stt');

            const result = await API.processAudio(audioBlob, language, personaId);

            // All stages complete
            this.setLoadingStage('done');

            // Hide the empty state
            if (this.dom.chatEmpty) {
                this.dom.chatEmpty.style.display = 'none';
            }

            // Add the conversation to the chat
            this.addChatPair(result);

            // Auto-play the response audio
            if (result.audio_url) {
                Player.play(result.audio_url);
            }

            this.showToast(
                `Processed in ${(result.processing_time_ms / 1000).toFixed(1)}s`,
                'success'
            );

        } catch (err) {
            console.error('[UI] Processing failed:', err);
            this.showToast(`Error: ${err.message}`, 'error');
        } finally {
            this.hideLoading();
            this.isProcessing = false;
        }
    },

    /**
     * Add a user question + AI response pair to the chat.
     */
    addChatPair(result) {
        const pair = document.createElement('div');
        pair.className = 'chat-pair';

        // User bubble
        const userBubble = document.createElement('div');
        userBubble.className = 'chat-bubble bubble-user';
        userBubble.innerHTML = `
            <span class="bubble-label">You</span>
            <div class="bubble-text">${this.escapeHtml(result.transcript)}</div>
        `;

        // AI bubble
        const persona = this.personas.find(p => p.id === this.selectedPersonaId);
        const personaName = persona ? persona.name : 'AI';

        const aiBubble = document.createElement('div');
        aiBubble.className = 'chat-bubble bubble-ai';

        // Clean up reply text for display (remove watermark brackets)
        const cleanReply = result.reply_text.replace(/\[.*?\]/g, '').trim();

        let aiContent = `
            <span class="bubble-label">${this.escapeHtml(personaName)}</span>
            <div class="bubble-text">${this.escapeHtml(cleanReply)}</div>
        `;

        // Add audio player
        if (result.audio_url) {
            aiContent += `
                <div class="bubble-audio">
                    <audio controls preload="metadata" src="${result.audio_url}"></audio>
                </div>
            `;
        }

        // Add metadata
        aiContent += `
            <div class="bubble-meta">
                <span>${(result.processing_time_ms / 1000).toFixed(1)}s</span>
                <span>${result.target_language.toUpperCase()}</span>
                ${result.context_used && result.context_used.length > 0
                    ? `<span>RAG: ${result.context_used.length} docs</span>`
                    : ''}
            </div>
            <div class="bubble-watermark">AI-Generated Response — Digital Twin</div>
        `;

        aiBubble.innerHTML = aiContent;

        pair.appendChild(userBubble);
        pair.appendChild(aiBubble);

        this.dom.chatMessages.appendChild(pair);

        // Scroll to bottom
        this.dom.chatMessages.scrollTop = this.dom.chatMessages.scrollHeight;
    },

    /**
     * Clear the chat history.
     */
    clearChat() {
        this.dom.chatMessages.innerHTML = '';

        // Re-add empty state
        const empty = document.createElement('div');
        empty.className = 'chat-empty';
        empty.id = 'chat-empty';
        empty.innerHTML = `
            <p>Press and hold the microphone button to ask a question.</p>
            <p class="chat-empty-hint">Your conversation will appear here.</p>
        `;
        this.dom.chatMessages.appendChild(empty);
        this.dom.chatEmpty = empty;
    },

    // --- Loading Overlay ---

    showLoading() {
        this.dom.loadingOverlay.classList.add('visible');
        // Reset all stages
        document.querySelectorAll('.stage').forEach(s => {
            s.className = 'stage';
        });
    },

    hideLoading() {
        this.dom.loadingOverlay.classList.remove('visible');
    },

    setLoadingStage(stage) {
        const stages = ['stt', 'rag', 'llm', 'tts'];
        const stageIndex = stages.indexOf(stage);

        stages.forEach((s, i) => {
            const el = document.getElementById(`stage-${s}`);
            if (!el) return;

            if (stage === 'done') {
                el.className = 'stage done';
            } else if (i < stageIndex) {
                el.className = 'stage done';
            } else if (i === stageIndex) {
                el.className = 'stage active';
            } else {
                el.className = 'stage';
            }
        });
    },

    // --- Toast Notifications ---

    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;

        container.appendChild(toast);

        // Auto-remove after 4 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(40px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    // --- Helpers ---

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    // --- Create Persona Modal ---

    openCreateModal() {
        this.dom.createModal.classList.add('visible');
        document.getElementById('cp-name').focus();
    },

    closeCreateModal() {
        this.dom.createModal.classList.remove('visible');
        this.dom.createForm.reset();
    },

    /**
     * Parse a comma-separated string into a trimmed array.
     * "Patient, Uses analogies, Encouraging" → ["Patient", "Uses analogies", "Encouraging"]
     */
    _parseCommaSeparated(value) {
        if (!value || !value.trim()) return [];
        return value.split(',').map(s => s.trim()).filter(s => s.length > 0);
    },

    async submitCreatePersona() {
        const name = document.getElementById('cp-name').value.trim();
        if (!name) {
            this.showToast('Name is required', 'error');
            return;
        }

        // Build the persona data object
        const personaData = {
            name: name,
            role: document.getElementById('cp-role').value.trim() || null,
            institution: document.getElementById('cp-institution').value.trim() || null,
            personality_traits: this._parseCommaSeparated(document.getElementById('cp-personality').value),
            knowledge_areas: this._parseCommaSeparated(document.getElementById('cp-knowledge').value),
            speaking_style: document.getElementById('cp-style').value.trim() || null,
            constraints: this._parseCommaSeparated(document.getElementById('cp-constraints').value),
        };

        // Disable submit button while creating
        const submitBtn = this.dom.createForm.querySelector('.btn-primary');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Creating...';

        try {
            const created = await API.createPersona(personaData);

            this.showToast(`Persona "${created.name}" created!`, 'success');
            this.closeCreateModal();

            // Reload personas and auto-select the new one
            await this.loadPersonas();
            this.dom.personaSelect.value = created.id;
            this.onPersonaChange();

        } catch (err) {
            console.error('[UI] Failed to create persona:', err);
            this.showToast(`Failed: ${err.message}`, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Create Persona';
        }
    },
};

// --- Boot ---
document.addEventListener('DOMContentLoaded', () => {
    UI.init();
});
