/**
 * Real-time Word Highlighting for Reading Practice
 * 
 * This module provides functionality for real-time word highlighting
 * as a student reads text aloud. It uses the Web Speech API for
 * speech recognition and matches spoken words with the text.
 */

class RealtimeHighlighter {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        if (!this.container) {
            console.error(`Container element with ID ${containerId} not found`);
            return;
        }
        
        // Configuration options
        this.options = {
            apiEndpoint: '/api',
            highlightCurrent: true,
            autoScroll: true,
            preferServerRecognition: true,
            ...options
        };
        
        // State variables
        this.isReading = false;
        this.isPaused = false;
        this.isServerRecognition = false;
        this.currentWordIndex = 0;
        this.totalWords = 0;
        this.trackingData = null;
        this.originalText = '';
        this.transcriptText = ''; // Store the current transcript
        this.recognitionRestartAttempts = 0;
        this.maxRecognitionRestarts = 5; // Maximum number of automatic restarts
        
        // Speech recognition
        this.recognition = null;
        this.isRecognitionSupported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window;
        
        // Initialize UI elements
        this.initUI();
        
        // Initialize speech recognition if supported
        if (this.isRecognitionSupported) {
            this.initSpeechRecognition();
        } else {
            this.showError("Speech recognition is not supported in your browser. Please try Chrome, Edge, or Safari.");
        }
    }
    
    initUI() {
        // Create UI elements for the component
        this.container.innerHTML = `
            <div class="reading-controls mb-3">
                <button id="start-reading-btn" class="btn btn-primary">Start Reading</button>
                <button id="pause-reading-btn" class="btn btn-secondary" disabled>Pause</button>
                <button id="stop-reading-btn" class="btn btn-danger" disabled>Stop</button>
                <span id="microphone-status" class="mic-indicator ml-3" style="display: none;"></span>
            </div>
            <div class="reading-text-container mb-4">
                <div id="reading-text"></div>
            </div>
            <div class="transcript-container">
                <h5>Your Speech <span id="recognition-source" class="badge bg-secondary"></span></h5>
                <div id="speech-transcript" class="transcript-text">Speech will appear here as you read...</div>
            </div>
            <div id="reading-results" class="mt-4" style="display:none;"></div>
        `;
        
        // Add event listeners
        document.getElementById('start-reading-btn').addEventListener('click', () => this.startReading());
        document.getElementById('pause-reading-btn').addEventListener('click', () => this.pauseReading());
        document.getElementById('stop-reading-btn').addEventListener('click', () => this.stopReading());
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .reading-controls {
                margin-bottom: 15px;
            }
            .reading-text-container {
                background-color: #fff;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 20px;
                margin-bottom: 20px;
                line-height: 1.8;
                font-size: 18px;
                overflow-y: auto;
                max-height: 300px;
            }
            .transcript-container {
                background-color: #f8f9fa;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 20px;
            }
            .transcript-text {
                min-height: 60px;
                line-height: 1.6;
                color: #333;
                font-style: italic;
            }
            .recognition-active {
                border-color: #4caf50 !important;
                box-shadow: 0 0 5px rgba(76, 175, 80, 0.5);
            }
            .highlight-interim {
                background-color: #e3f2fd;
                padding: 2px 0;
            }
            #reading-results {
                background-color: #f5f5f5;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 15px;
            }
            .mic-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                margin-left: 10px;
                border-radius: 50%;
                background-color: #ccc;
            }
            .mic-active {
                background-color: #f44336;
                animation: pulse 1.5s infinite;
            }
            @keyframes pulse {
                0% { transform: scale(1); opacity: 1; }
                50% { transform: scale(1.3); opacity: 0.7; }
                100% { transform: scale(1); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }
    
    initSpeechRecognition() {
        // Set up the Web Speech API
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        this.recognition = new SpeechRecognition();
        
        // Configure recognition
        this.recognition.continuous = true;
        this.recognition.interimResults = true;
        this.recognition.lang = 'en-US';
        this.recognition.maxAlternatives = 3; // Get multiple alternatives
        
        // Set up event handlers
        this.recognition.onstart = () => {
            this.updateStatus('Listening...');
            this.setMicrophoneStatus(true);
            document.querySelector('.reading-text-container').classList.add('recognition-active');
            // Clear previous transcript when starting new session
            if (!this.isPaused) {
                this.transcriptText = '';
                this.updateTranscript('');
            }
        };
        
        this.recognition.onend = () => {
            if (this.isReading && !this.isPaused) {
                // Check if we should restart recognition or stop due to too many restart attempts
                if (this.recognitionRestartAttempts < this.maxRecognitionRestarts) {
                    // Restart recognition if we're still in reading mode
                    this.recognitionRestartAttempts++;
                    setTimeout(() => {
                        try {
                            this.recognition.start();
                            this.updateStatus(`Listening... (restart ${this.recognitionRestartAttempts}/${this.maxRecognitionRestarts})`);
                        } catch (e) {
                            console.error("Error restarting recognition:", e);
                            this.updateStatus('Recognition error: ' + e.message);
                            this.setMicrophoneStatus(false);
                        }
                    }, 300); // Brief delay before restarting
                } else {
                    // Too many restart attempts, warn user
                    this.updateStatus('Speech recognition stopped. Too many restarts.');
                    this.showError('Speech recognition has stopped due to too many disconnections. Please stop and try again.');
                    this.setMicrophoneStatus(false);
                }
            } else {
                this.updateStatus('Stopped listening');
                this.setMicrophoneStatus(false);
                document.querySelector('.reading-text-container').classList.remove('recognition-active');
            }
        };
        
        this.recognition.onresult = (event) => {
            // Process speech recognition results
            const results = event.results;
            
            if (results.length > 0) {
                // Get the most recent result
                const result = results[results.length - 1];
                
                // Get best transcript
                const transcript = result[0].transcript;
                
                // Show interim results with different styling
                if (!result.isFinal) {
                    this.updateTranscript(
                        this.transcriptText + 
                        ` <span class="highlight-interim">${transcript}</span>`
                    );
                } else {
                    console.log('Final result:', transcript);
                    
                    // Add to full transcript
                    if (this.transcriptText) {
                        this.transcriptText += ' ' + transcript;
                    } else {
                        this.transcriptText = transcript;
                    }
                    
                    this.updateTranscript(this.transcriptText.trim());
                    this.processSpeechResult(transcript);
                }
            }
        };
        
        this.recognition.onerror = (event) => {
            console.error('Speech recognition error', event.error);
            if (event.error === 'no-speech') {
                // This is common and not critical, don't show error
                this.updateStatus('No speech detected. Keep reading...');
            } else if (event.error === 'audio-capture') {
                this.showError('No microphone detected. Please check your microphone settings.');
                this.stopReading();
            } else if (event.error === 'not-allowed') {
                this.showError('Microphone access denied. Please allow microphone access to use this feature.');
                this.stopReading();
            } else if (event.error === 'network') {
                this.showError('Network error occurred. Check your internet connection.');
                // Don't auto-stop - it might recover
            } else {
                this.showError(`Speech recognition error: ${event.error}`);
                
                if (event.error === 'aborted' || event.error === 'service-not-allowed') {
                    this.stopReading();
                }
            }
        };
    }
    
    async prepareText(text) {
        try {
            // Reset state
            this.recognitionRestartAttempts = 0;
            this.isServerRecognition = false;
            this.updateRecognitionSource('Not started');

            // Call the API to prepare text for highlighting
            const response = await fetch(`${this.options.apiEndpoint}/prepare-realtime-tracking`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    text: text
                })
            });
            
            if (!response.ok) {
                throw new Error(`API error: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to prepare text');
            }
            
            // Set up the reading text
            const readingTextElement = document.getElementById('reading-text');
            readingTextElement.innerHTML = data.tracking_html;
            
            // Store data
            this.totalWords = data.word_count;
            this.originalText = text;
            this.currentWordIndex = 0;
            
            // Reset transcript
            this.transcriptText = '';
            this.updateTranscript('');
            
            // Clear any previous results
            document.getElementById('reading-results').style.display = 'none';
            
            return true;
        } catch (error) {
            this.showError(`Error preparing text: ${error.message}`);
            return false;
        }
    }
    
    startReading() {
        if (!this.isRecognitionSupported) {
            this.showError("Speech recognition is not supported in your browser");
            return;
        }
        
        if (this.isPaused) {
            // Resume from pause
            this.isPaused = false;
            this.startRecognition();
        } else {
            // Start new reading session
            this.isReading = true;
            this.currentWordIndex = 0;
            
            // Update UI
            document.getElementById('start-reading-btn').disabled = true;
            document.getElementById('pause-reading-btn').disabled = false;
            document.getElementById('stop-reading-btn').disabled = false;
            document.getElementById('reading-results').style.display = 'none';
            
            // Start recognition
            this.startRecognition();
            
            // Highlight the first word
            if (this.options.highlightCurrent) {
                this.highlightCurrentWord(0);
            }
        }
    }
    
    async startRecognition() {
        // Try to use server-side recognition first if preferred
        if (this.options.preferServerRecognition) {
            try {
                this.updateStatus('Starting speech recognition...');
                
                // Create a short audio snippet for testing recognition
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const recorder = new MediaRecorder(stream);
                const audioChunks = [];
                
                recorder.addEventListener('dataavailable', e => {
                    audioChunks.push(e.data);
                });
                
                // The promise resolves when we have audio data
                const audioPromise = new Promise((resolve) => {
                    recorder.addEventListener('stop', () => {
                        const audioBlob = new Blob(audioChunks);
                        // Convert to base64 for sending to the server
                        const reader = new FileReader();
                        reader.readAsDataURL(audioBlob);
                        reader.onloadend = () => {
                            resolve(reader.result);
                        };
                    });
                });
                
                // Record a short audio sample
                recorder.start();
                setTimeout(() => recorder.stop(), 500);
                
                // Get the audio data
                const audioData = await audioPromise;
                
                // Release the media stream
                stream.getTracks().forEach(track => track.stop());
                
                // Try to use server-side recognition
                const formData = new FormData();
                formData.append('audio_data', audioData);
                
                const response = await fetch(`${this.options.apiEndpoint}/transcribe-audio-realtime`, {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`Server returned status ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.success && !data.use_browser_recognition) {
                    // Server-side recognition is available, use it
                    this.isServerRecognition = true;
                    this.updateStatus('Using server-side speech recognition');
                    this.updateRecognitionSource('Server');
                    // Restart stream for continuous recording
                    const newStream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    this.startServerRecognition(newStream);
                    return;
                } else {
                    // Server recognition not available, use browser
                    console.log('Falling back to browser speech recognition:', data.error || 'Server opted for browser recognition');
                    this.updateStatus('Using browser speech recognition');
                    this.updateRecognitionSource('Browser');
                }
            } catch (error) {
                console.error('Error trying server recognition:', error);
                this.updateStatus('Using browser speech recognition');
                this.updateRecognitionSource('Browser');
            }
        } else {
            // Browser recognition preferred
            this.updateStatus('Using browser speech recognition');
            this.updateRecognitionSource('Browser');
        }
        
        // Start browser-based recognition
        try {
            this.recognition.start();
            this.updateStatus('Listening. Begin reading aloud...');
        } catch (error) {
            this.showError(`Could not start speech recognition: ${error.message}`);
            this.updateStatus('Failed to start speech recognition');
            this.setMicrophoneStatus(false);
        }
    }
    
    startServerRecognition(existingStream) {
        // Set up continuous recording for server-side recognition
        this.setMicrophoneStatus(true);
        this.updateStatus('Server listening. Begin reading aloud...');
        document.querySelector('.reading-text-container').classList.add('recognition-active');
        
        // Save the stream for cleanup later
        this.serverStream = existingStream;
        
        // Get audio stream if not provided
        const setupRecording = async (stream) => {
            try {
                // Set up MediaRecorder
                const recorder = new MediaRecorder(stream);
                this.serverRecorder = recorder;
                const audioChunks = [];
                
                recorder.addEventListener('dataavailable', e => {
                    audioChunks.push(e.data);
                });
                
                recorder.addEventListener('stop', async () => {
                    if (!this.isReading || this.isPaused) return;
                    
                    try {
                        // Convert audio to base64
                        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                        const reader = new FileReader();
                        reader.readAsDataURL(audioBlob);
                        
                        reader.onloadend = async () => {
                            if (!this.isReading) return;
                            
                            try {
                                const audioData = reader.result;
                                
                                // Send to server for transcription
                                const formData = new FormData();
                                formData.append('audio_data', audioData);
                                
                                const response = await fetch(`${this.options.apiEndpoint}/transcribe-audio-realtime`, {
                                    method: 'POST',
                                    body: formData
                                });
                                
                                if (!response.ok) {
                                    throw new Error(`Server returned status ${response.status}`);
                                }
                                
                                const data = await response.json();
                                
                                if (data.success) {
                                    // Use transcription result
                                    const transcript = data.transcription || '';
                                    
                                    if (transcript && transcript.trim()) {
                                        // Add to transcript
                                        if (this.transcriptText) {
                                            this.transcriptText += ' ' + transcript;
                                        } else {
                                            this.transcriptText = transcript;
                                        }
                                        
                                        this.updateTranscript(this.transcriptText.trim());
                                        this.processSpeechResult(transcript);
                                    }
                                    
                                    // Continue recording if still reading
                                    if (this.isReading && !this.isPaused && this.isServerRecognition) {
                                        audioChunks.length = 0; // Clear chunks
                                        recorder.start();
                                        setTimeout(() => {
                                            if (recorder.state === 'recording') {
                                                recorder.stop();
                                            }
                                        }, 3000); // Record 3 seconds at a time
                                    }
                                } else {
                                    // Server recognition failed, fall back to browser
                                    console.log('Falling back to browser recognition:', data.error || 'Unknown error');
                                    this.isServerRecognition = false;
                                    this.updateStatus('Switched to browser recognition');
                                    this.updateRecognitionSource('Browser');
                                    stream.getTracks().forEach(track => track.stop());
                                    this.recognition.start();
                                }
                            } catch (err) {
                                console.error('Error in server recognition cycle:', err);
                                // Fall back to browser recognition
                                this.isServerRecognition = false;
                                this.updateStatus('Error with server recognition, switched to browser');
                                this.updateRecognitionSource('Browser');
                                stream.getTracks().forEach(track => track.stop());
                                this.recognition.start();
                            }
                        };
                    } catch (err) {
                        console.error('Error handling recorded audio:', err);
                        this.showError('Error processing audio: ' + err.message);
                    }
                });
                
                // Start recording
                audioChunks.length = 0;
                recorder.start();
                setTimeout(() => {
                    if (recorder.state === 'recording') {
                        recorder.stop();
                    }
                }, 3000); // Record 3 seconds at a time
                
            } catch (err) {
                console.error('Error setting up server recording:', err);
                this.showError('Error setting up audio recording: ' + err.message);
                this.isServerRecognition = false;
                this.updateRecognitionSource('Browser');
                // Fall back to browser recognition
                this.recognition.start();
            }
        };
        
        setupRecording(existingStream);
    }
    
    pauseReading() {
        if (this.isReading) {
            this.isPaused = true;
            
            if (this.isServerRecognition && this.serverRecorder) {
                if (this.serverRecorder.state === 'recording') {
                    this.serverRecorder.stop();
                }
            } else {
                this.recognition.stop();
            }
            
            this.updateStatus('Paused');
            this.setMicrophoneStatus(false);
            
            // Update button states
            document.getElementById('start-reading-btn').disabled = false;
            document.getElementById('pause-reading-btn').disabled = true;
        }
    }
    
    async stopReading() {
        if (this.isReading) {
            // Stop recognition
            this.isReading = false;
            this.isPaused = false;
            
            if (this.isServerRecognition && this.serverRecorder) {
                if (this.serverRecorder.state === 'recording') {
                    this.serverRecorder.stop();
                }
                // Stop any streams
                if (this.serverStream) {
                    this.serverStream.getTracks().forEach(track => track.stop());
                }
            } else {
                this.recognition.stop();
            }
            
            // Update UI
            document.getElementById('start-reading-btn').disabled = false;
            document.getElementById('pause-reading-btn').disabled = true;
            document.getElementById('stop-reading-btn').disabled = true;
            
            this.updateStatus('Finalizing results...');
            this.setMicrophoneStatus(false);
            
            // Finalize the reading session and get results
            await this.finalizeReading();
        }
    }
    
    async processSpeechResult(speechText) {
        if (!speechText || !this.isReading) return;
        
        try {
            // Send to server for processing
            const response = await fetch(`${this.options.apiEndpoint}/process-speech-result`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    speech_text: speechText,
                    current_index: this.currentWordIndex
                })
            });
            
            if (!response.ok) {
                // Try to get more detailed error information
                const errorData = await response.json().catch(() => ({}));
                throw new Error(`API error ${response.status}: ${errorData.error || response.statusText}`);
            }
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to process speech');
            }
            
            // Update word statuses
            if (data.updated_words && data.updated_words.length > 0) {
                for (const update of data.updated_words) {
                    this.updateWordStatus(update.index, update.status);
                }
                
                // Update current word index if provided
                if (data.next_word_index !== undefined) {
                    this.currentWordIndex = data.next_word_index;
                    this.highlightCurrentWord(this.currentWordIndex);
                    
                    // Auto scroll if enabled
                    if (this.options.autoScroll) {
                        this.scrollToCurrentWord(this.currentWordIndex);
                    }
                }
            }
        } catch (error) {
            console.error('Error processing speech result:', error);
            // Continue reading even if there's an error processing a speech segment
            // Just log the error rather than completely stopping
        }
    }
    
    updateWordStatus(wordIndex, status) {
        const wordElement = document.getElementById(`word-${wordIndex}`);
        if (wordElement) {
            // Remove existing status classes
            wordElement.classList.remove('pending', 'current', 'correct', 'incorrect', 'skipped');
            // Add the new status class
            wordElement.classList.add(status);
        }
    }
    
    highlightCurrentWord(wordIndex) {
        // Remove current highlight from all words
        document.querySelectorAll('.current').forEach(el => {
            el.classList.remove('current');
        });
        
        // Add current highlight to the current word
        const wordElement = document.getElementById(`word-${wordIndex}`);
        if (wordElement) {
            wordElement.classList.add('current');
        }
    }
    
    scrollToCurrentWord(wordIndex) {
        const wordElement = document.getElementById(`word-${wordIndex}`);
        if (wordElement) {
            // Scroll the word into view with some padding
            wordElement.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }
    }
    
    updateTranscript(text) {
        const transcriptElement = document.getElementById('speech-transcript');
        if (transcriptElement) {
            if (text && text.trim()) {
                transcriptElement.innerHTML = text; // Use innerHTML to support highlighted interim results
            } else {
                transcriptElement.textContent = 'Speech will appear here as you read...';
            }
        }
    }
    
    async finalizeReading() {
        try {
            // Call API to finalize the reading session
            const response = await fetch(`${this.options.apiEndpoint}/finalize-reading-tracking`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({})
            });
            
            if (!response.ok) {
                // Try to get more detailed error information
                const errorData = await response.json().catch(() => ({}));
                throw new Error(`API error ${response.status}: ${errorData.error || response.statusText}`);
            }
            
            const data = await response.json();
            
            if (!data.success) {
                throw new Error(data.error || 'Failed to finalize reading');
            }
            
            // Display final results
            const resultsElement = document.getElementById('reading-results');
            if (resultsElement) {
                resultsElement.innerHTML = data.final_html || 'No analysis available';
                resultsElement.style.display = 'block';
                
                // Scroll to the results
                resultsElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
            
            // Update status
            if (data.statistics) {
                this.updateStatus('Reading completed. ' +
                    `Accuracy: ${data.statistics.accuracy_percentage}% ` +
                    `(${data.statistics.correct}/${data.statistics.total_words} words correct)`);
            } else {
                this.updateStatus('Reading completed. Analysis available below.');
            }
            
            return data.statistics || null;
        } catch (error) {
            console.error('Error finalizing reading:', error);
            this.showError(`Error finalizing reading: ${error.message}`);
            
            // Return minimal info on error
            return null;
        }
    }
    
    updateStatus(message) {
        // Dispatch status update event
        const event = new CustomEvent('reading-status-update', {
            detail: { message: message }
        });
        this.container.dispatchEvent(event);
    }
    
    updateRecognitionSource(source) {
        const sourceElement = document.getElementById('recognition-source');
        if (sourceElement) {
            sourceElement.textContent = source;
        }
    }
    
    setMicrophoneStatus(active) {
        const micIndicator = document.getElementById('microphone-status');
        if (micIndicator) {
            micIndicator.style.display = active ? 'inline-block' : 'none';
            if (active) {
                micIndicator.classList.add('mic-active');
            } else {
                micIndicator.classList.remove('mic-active');
            }
        }
    }
    
    showError(message) {
        console.error(message);
        
        // Dispatch error event for parent component to handle
        const event = new CustomEvent('reading-error', {
            detail: { message: message }
        });
        
        this.container.dispatchEvent(event);
    }
}

// Make available globally
window.RealtimeHighlighter = RealtimeHighlighter; 