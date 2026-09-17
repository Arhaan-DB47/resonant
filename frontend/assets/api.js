/**
 * api.js -- Backend API Client
 *
 * All fetch calls to the FastAPI backend are centralized here.
 * Other scripts import these functions instead of calling fetch directly.
 */

const API = {
    BASE: '/api',

    /**
     * Check server health and LLM availability.
     * @returns {Promise<{status, version, services}>}
     */
    async healthCheck() {
        const res = await fetch(`${this.BASE}/health`);
        if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
        return res.json();
    },

    /**
     * List all personas.
     * @returns {Promise<Array<{id, name, role, institution, ...}>>}
     */
    async getPersonas() {
        const res = await fetch(`${this.BASE}/personas`);
        if (!res.ok) throw new Error(`Failed to load personas: ${res.status}`);
        return res.json();
    },

    /**
     * Get a specific persona by ID.
     * @param {number} id
     * @returns {Promise<{id, name, role, institution, ...}>}
     */
    async getPersona(id) {
        const res = await fetch(`${this.BASE}/personas/${id}`);
        if (!res.ok) throw new Error(`Persona ${id} not found`);
        return res.json();
    },

    /**
     * Send audio to the pipeline and get transcript + reply + audio back.
     * @param {Blob} audioBlob - The recorded audio
     * @param {string} language - Target language code (e.g., "en")
     * @param {number} personaId - Which persona to use
     * @returns {Promise<{transcript, reply_text, audio_url, target_language, context_used, processing_time_ms}>}
     */
    async processAudio(audioBlob, language, personaId) {
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.webm');
        formData.append('target_language', language);
        formData.append('persona_id', personaId);

        const res = await fetch(`${this.BASE}/process`, {
            method: 'POST',
            body: formData,
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `Processing failed: ${res.status}`);
        }

        return res.json();
    },

    /**
     * Create a new persona.
     * @param {Object} personaData - {name, role, institution, personality_traits, ...}
     * @returns {Promise<{id, name, role, ...}>}
     */
    async createPersona(personaData) {
        const res = await fetch(`${this.BASE}/personas`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(personaData),
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `Failed to create persona: ${res.status}`);
        }

        return res.json();
    },

    /**
     * Get conversation history for a persona.
     * @param {number} personaId
     * @param {number} limit
     * @returns {Promise<Array>}
     */
    async getHistory(personaId, limit = 20) {
        const res = await fetch(`${this.BASE}/personas/${personaId}/history?limit=${limit}`);
        if (!res.ok) throw new Error(`Failed to load history: ${res.status}`);
        return res.json();
    },
};
