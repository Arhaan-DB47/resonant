/**
 * player.js -- Audio Playback Helper
 *
 * Handles playing response audio files returned by the pipeline.
 */

const Player = {
    /** @type {HTMLAudioElement|null} */
    currentAudio: null,

    /**
     * Play an audio file from the server.
     * @param {string} audioUrl - URL path like "/outputs/response_xxx.mp3"
     */
    play(audioUrl) {
        // Stop any currently playing audio
        this.stop();

        this.currentAudio = new Audio(audioUrl);

        this.currentAudio.addEventListener('error', (e) => {
            console.error('[Player] Audio playback error:', e);
            UI.showToast('Failed to play audio response', 'error');
        });

        this.currentAudio.play().catch((err) => {
            console.warn('[Player] Autoplay blocked:', err.message);
        });
    },

    /**
     * Stop the currently playing audio.
     */
    stop() {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
        }
    },

    /**
     * Create an audio player element for embedding in chat bubbles.
     * @param {string} audioUrl
     * @returns {HTMLElement}
     */
    createPlayerElement(audioUrl) {
        const container = document.createElement('div');
        container.className = 'bubble-audio';

        const audio = document.createElement('audio');
        audio.controls = true;
        audio.preload = 'metadata';
        audio.src = audioUrl;

        container.appendChild(audio);
        return container;
    },
};
