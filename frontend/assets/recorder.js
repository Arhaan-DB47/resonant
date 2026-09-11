/**
 * recorder.js -- Audio Recorder using MediaRecorder API
 *
 * Handles microphone access, recording, and producing audio blobs.
 * Uses the browser's MediaRecorder API to capture audio from the mic.
 *
 * Usage:
 *   Recorder.init()        → Request microphone permission
 *   Recorder.start()       → Start recording
 *   Recorder.stop()        → Stop and return audio Blob
 */

const Recorder = {
    /** @type {MediaRecorder|null} */
    mediaRecorder: null,

    /** @type {MediaStream|null} */
    stream: null,

    /** @type {Blob[]} */
    chunks: [],

    /** @type {boolean} */
    isRecording: false,

    /** @type {Function|null} Callback when recording stops */
    _onStop: null,

    /**
     * Initialize the recorder — request microphone permission.
     * @returns {Promise<boolean>} True if mic access was granted
     */
    async init() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,        // Mono
                    sampleRate: 16000,       // 16kHz (optimal for Whisper)
                    echoCancellation: true,
                    noiseSuppression: true,
                },
            });
            console.log('[Recorder] Microphone access granted');
            return true;
        } catch (err) {
            console.error('[Recorder] Microphone access denied:', err);
            return false;
        }
    },

    /**
     * Start recording audio from the microphone.
     */
    start() {
        if (!this.stream) {
            console.error('[Recorder] Not initialized. Call init() first.');
            return;
        }

        this.chunks = [];

        // Pick the best supported MIME type
        const mimeType = this._getBestMimeType();

        this.mediaRecorder = new MediaRecorder(this.stream, {
            mimeType: mimeType,
        });

        this.mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) {
                this.chunks.push(e.data);
            }
        };

        this.mediaRecorder.onstop = () => {
            const blob = new Blob(this.chunks, { type: mimeType });
            console.log(`[Recorder] Stopped. Blob size: ${(blob.size / 1024).toFixed(1)} KB`);

            if (this._onStop) {
                this._onStop(blob);
                this._onStop = null;
            }
        };

        this.mediaRecorder.start();
        this.isRecording = true;
        console.log(`[Recorder] Started recording (${mimeType})`);
    },

    /**
     * Stop recording and return the audio blob.
     * @returns {Promise<Blob>} The recorded audio
     */
    stop() {
        return new Promise((resolve) => {
            if (!this.mediaRecorder || this.mediaRecorder.state === 'inactive') {
                resolve(null);
                return;
            }

            this._onStop = resolve;
            this.mediaRecorder.stop();
            this.isRecording = false;
        });
    },

    /**
     * Get the best supported audio MIME type.
     * Chrome supports webm/opus, Firefox supports ogg/opus, Safari supports mp4.
     */
    _getBestMimeType() {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
        ];

        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                return type;
            }
        }

        return 'audio/webm'; // Fallback
    },
};
