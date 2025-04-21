document.addEventListener('DOMContentLoaded', function() {
    // Global state
    const state = {
        original_text: '',
        passage_title: '',
        spoken_text: '',
        transcription_result: null,
        recording: null,
        audio_duration: 0,
        grammar_test: null,
        grammar_evaluation: null,
        analysis_result: null,
        mediaRecorder: null,
        audioChunks: [],
        recordingTimer: null,
        recordingTime: 0
    };

    // Navigation elements
    const navButtons = {
        textInput: document.getElementById('nav-text-input'),
        grammarTest: document.getElementById('nav-grammar-test'),
        readingAssessment: document.getElementById('nav-reading-assessment'),
        results: document.getElementById('nav-results')
    };

    // Content sections
    const sections = {
        textInput: document.getElementById('section-text-input'),
        grammarTest: document.getElementById('section-grammar-test'),
        readingAssessment: document.getElementById('section-reading-assessment'),
        results: document.getElementById('section-results')
    };

    // Form elements
    const forms = {
        uploadForm: document.getElementById('upload-form'),
        textForm: document.getElementById('text-form'),
        fileUpload: document.getElementById('file-upload'),
        passageTitle: document.getElementById('passage-title'),
        passageText: document.getElementById('passage-text')
    };

    // Button elements
    const buttons = {
        continueBtn: document.getElementById('continue-btn'),
        continueToReading: document.getElementById('continue-to-reading'),
        startRecording: document.getElementById('start-recording'),
        stopRecording: document.getElementById('stop-recording'),
        analyzeReading: document.getElementById('analyze-reading'),
        submitGrammar: document.getElementById('submit-grammar'),
        restartAssessment: document.getElementById('restart-assessment'),
        printResults: document.getElementById('print-results')
    };

    // Other elements
    const elements = {
        studentName: document.getElementById('student-name'),
        gradeLevel: document.getElementById('grade-level'),
        previewCard: document.getElementById('text-preview-card'),
        previewTitle: document.getElementById('preview-title'),
        previewText: document.getElementById('preview-text'),
        grammarLoading: document.getElementById('grammar-loading'),
        grammarTestContainer: document.getElementById('grammar-test-container'),
        grammarQuestions: document.getElementById('grammar-questions'),
        grammarResults: document.getElementById('grammar-results'),
        readingPassageTitle: document.getElementById('reading-passage-title'),
        readingPassageText: document.getElementById('reading-passage-text'),
        recordingStatus: document.getElementById('recording-status'),
        recordingTime: document.getElementById('recording-time'),
        transcriptionLoading: document.getElementById('transcription-loading'),
        transcriptionResult: document.getElementById('transcription-result'),
        transcribedText: document.getElementById('transcribed-text'),
        alertsContainer: document.getElementById('alerts-container')
    };

    // Initialize the application
    function init() {
        // Set up event listeners
        setupNavigation();
        setupForms();
        setupButtons();
        setupRecording();
    }

    // Navigation setup
    function setupNavigation() {
        // Navigation between sections
        navButtons.textInput.addEventListener('click', () => showSection('textInput'));
        navButtons.grammarTest.addEventListener('click', () => showSection('grammarTest'));
        navButtons.readingAssessment.addEventListener('click', () => showSection('readingAssessment'));
        navButtons.results.addEventListener('click', () => showSection('results'));
    }

    // Form setup
    function setupForms() {
        // File upload form
        forms.uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            if (!forms.fileUpload.files[0]) {
                showAlert('Please select a file to upload.', 'warning');
                return;
            }
            
            const formData = new FormData();
            formData.append('file', forms.fileUpload.files[0]);
            formData.append('grade_level', elements.gradeLevel.value);
            
            showAlert('Uploading and processing file...', 'info');
            
            fetch('/api/extract-text', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    state.original_text = data.text;
                    state.passage_title = data.title;
                    
                    // Show the preview
                    elements.previewTitle.textContent = data.title;
                    elements.previewText.textContent = data.text;
                    elements.previewCard.classList.remove('d-none');
                    
                    showAlert('Text successfully extracted!', 'success');
                } else {
                    showAlert(data.error || 'Error extracting text.', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Error processing file. Please try again.', 'danger');
            });
        });
        
        // Direct text input form
        forms.textForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const title = forms.passageTitle.value || 'Custom Passage';
            const text = forms.passageText.value;
            
            if (!text) {
                showAlert('Please enter text for assessment.', 'warning');
                return;
            }
            
            fetch('/api/save-text', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    title: title,
                    text: text,
                    grade_level: elements.gradeLevel.value
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    state.original_text = data.text;
                    state.passage_title = data.title;
                    
                    // Show the preview
                    elements.previewTitle.textContent = data.title;
                    elements.previewText.textContent = data.text;
                    elements.previewCard.classList.remove('d-none');
                    
                    showAlert('Text successfully saved!', 'success');
                } else {
                    showAlert(data.error || 'Error saving text.', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showAlert('Error saving text. Please try again.', 'danger');
            });
        });
    }

    // Button setup
    function setupButtons() {
        // Continue to Grammar Test button
        buttons.continueBtn.addEventListener('click', function() {
            showSection('grammarTest');
            loadGrammarTest();
        });
        
        // Continue to Reading Assessment button
        buttons.continueToReading.addEventListener('click', function() {
            showSection('readingAssessment');
            prepareReadingSection();
        });
        
        // Submit Grammar Test button
        buttons.submitGrammar.addEventListener('click', function() {
            submitGrammarTest();
        });
        
        // Analyze Reading button
        buttons.analyzeReading.addEventListener('click', function() {
            analyzeReadingComprehensive();
        });
        
        // Restart Assessment button
        buttons.restartAssessment.addEventListener('click', function() {
            resetAssessment();
        });
        
        // Print Results button
        buttons.printResults.addEventListener('click', function() {
            window.print();
        });
    }

    // Recording setup
    function setupRecording() {
        // Start recording button
        buttons.startRecording.addEventListener('click', function() {
            startRecording();
        });
        
        // Stop recording button
        buttons.stopRecording.addEventListener('click', function() {
            stopRecording();
        });
    }

    // Show a specific section and update navigation
    function showSection(sectionName) {
        // Hide all sections
        for (const key in sections) {
            sections[key].classList.remove('active');
            navButtons[key].classList.remove('active');
        }
        
        // Show the selected section
        sections[sectionName].classList.add('active');
        navButtons[sectionName].classList.add('active');
    }

    // Display an alert message
    function showAlert(message, type = 'info', duration = 5000) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        elements.alertsContainer.appendChild(alertDiv);
        
        // Auto-dismiss after duration
        if (duration > 0) {
            setTimeout(() => {
                alertDiv.classList.remove('show');
                setTimeout(() => alertDiv.remove(), 300);
            }, duration);
        }
    }

    // Load grammar test
    function loadGrammarTest() {
        elements.grammarLoading.classList.remove('d-none');
        elements.grammarTestContainer.classList.add('d-none');
        elements.grammarResults.classList.add('d-none');
        
        const gradeLevel = elements.gradeLevel.value;
        
        fetch(`/api/grammar-test?grade_level=${gradeLevel}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                state.grammar_test = data.test;
                renderGrammarTest(data.test);
                
                elements.grammarLoading.classList.add('d-none');
                elements.grammarTestContainer.classList.remove('d-none');
            } else {
                showAlert(data.error || 'Error loading grammar test.', 'danger');
                elements.grammarLoading.classList.add('d-none');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Error loading grammar test. Please try again.', 'danger');
            elements.grammarLoading.classList.add('d-none');
        });
    }

    // Render grammar test questions
    function renderGrammarTest(test) {
        elements.grammarQuestions.innerHTML = '';
        
        test.questions.forEach((question, index) => {
            const questionDiv = document.createElement('div');
            questionDiv.className = 'question-container';
            
            const questionHTML = `
                <h6>Question ${index + 1}: ${question.question}</h6>
                <div class="options-container">
                    ${question.options.map((option, optionIndex) => `
                        <div class="form-check">
                            <input class="form-check-input" type="radio" name="question-${index}" id="option-${index}-${optionIndex}" value="${optionIndex}">
                            <label class="option-label" for="option-${index}-${optionIndex}">
                                ${option}
                            </label>
                        </div>
                    `).join('')}
                </div>
            `;
            
            questionDiv.innerHTML = questionHTML;
            elements.grammarQuestions.appendChild(questionDiv);
        });
    }

    // Submit grammar test answers
    function submitGrammarTest() {
        const answers = [];
        let allAnswered = true;
        
        // Collect answers
        state.grammar_test.questions.forEach((_, index) => {
            const selectedOption = document.querySelector(`input[name="question-${index}"]:checked`);
            
            if (selectedOption) {
                answers.push(selectedOption.value);
            } else {
                allAnswered = false;
                showAlert(`Please answer question ${index + 1}.`, 'warning');
            }
        });
        
        if (!allAnswered) {
            return;
        }
        
        // Submit answers
        fetch('/api/evaluate-grammar', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                answers: answers
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                state.grammar_evaluation = data.evaluation;
                displayGrammarResults(data.evaluation);
            } else {
                showAlert(data.error || 'Error evaluating grammar test.', 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showAlert('Error evaluating grammar test. Please try again.', 'danger');
        });
    }

    // Display grammar test results
    function displayGrammarResults(evaluation) {
        // Hide test and show results
        elements.grammarTestContainer.classList.add('d-none');
        elements.grammarResults.classList.remove('d-none');
        
        // Update basic scores
        document.getElementById('grammar-score').textContent = `${evaluation.score}%`;
        document.getElementById('grammar-correct').textContent = `${evaluation.correct_count}/${evaluation.total_questions}`;
        document.getElementById('grammar-level').textContent = evaluation.proficiency_level;
        
        // Update concepts mastered
        const conceptsMastered = document.getElementById('concepts-mastered');
        conceptsMastered.innerHTML = '';
        
        evaluation.concepts_mastered.forEach(concept => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = formatConceptName(concept);
            conceptsMastered.appendChild(li);
        });
        
        // Update concepts to improve
        const conceptsImprove = document.getElementById('concepts-improve');
        conceptsImprove.innerHTML = '';
        
        evaluation.concepts_to_improve.forEach(concept => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = formatConceptName(concept);
            conceptsImprove.appendChild(li);
        });
        
        // Update recommendations
        const recommendations = document.getElementById('grammar-recommendations');
        recommendations.innerHTML = '';
        
        evaluation.recommendations.forEach(recommendation => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = recommendation;
            recommendations.appendChild(li);
        });
    }

    // Format concept name for display
    function formatConceptName(concept) {
        return concept
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    }

    // Prepare reading assessment section
    function prepareReadingSection() {
        elements.readingPassageTitle.textContent = state.passage_title;
        
        // Reset any previous highlighting
        elements.readingPassageText.textContent = state.original_text;
        
        // Hide the error highlighting legend
        const legendElement = document.querySelector('.error-highlight-legend');
        if (legendElement) {
            legendElement.classList.add('d-none');
        }
        
        // Hide results
        elements.transcriptionResult.classList.add('d-none');
        elements.recordingStatus.classList.add('d-none');
        elements.transcriptionLoading.classList.add('d-none');
        
        // Show recording button
        buttons.startRecording.classList.remove('d-none');
        buttons.stopRecording.classList.add('d-none');
    }

    // Start audio recording
    function startRecording() {
        try {
            // Reset previous recording if it exists
            resetRecording();
            
            // Reset any highlighting in the reading passage
            elements.readingPassageText.textContent = state.original_text;
            
            // Hide the error highlighting legend
            const legendElement = document.querySelector('.error-highlight-legend');
            if (legendElement) {
                legendElement.classList.add('d-none');
            }
            
            // Show loading spinner and hide start button
            buttons.startRecording.classList.add('d-none');
            elements.recordingStatus.classList.remove('d-none');
            
            // Request user media
            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(stream => {
                    // Store the stream for later use
                    state.recording = stream;
                    
                    // Create a new MediaRecorder instance
                    state.mediaRecorder = new MediaRecorder(stream);
                    state.audioChunks = [];
                    
                    // Start the recording
                    state.mediaRecorder.start();
                    
                    // Event handler when data is available
                    state.mediaRecorder.addEventListener('dataavailable', event => {
                        state.audioChunks.push(event.data);
                    });
                    
                    // Event handler when recording is stopped
                    state.mediaRecorder.addEventListener('stop', () => {
                        processAudio();
                    });
                    
                    // Show the stop button
                    buttons.stopRecording.classList.remove('d-none');
                    
                    // Start the recording timer
                    state.recordingTime = 0;
                    state.recordingTimer = setInterval(updateRecordingTime, 1000);
                    
                    console.log('Recording started');
                })
                .catch(error => {
                    console.error('Error accessing microphone:', error);
                    showAlert('Error accessing microphone. Please ensure microphone permissions are allowed.', 'danger');
                    
                    // Reset UI
                    buttons.startRecording.classList.remove('d-none');
                    elements.recordingStatus.classList.add('d-none');
                });
        } catch (error) {
            console.error('Error starting recording:', error);
            showAlert('Error starting recording. Please try again.', 'danger');
            
            // Reset UI
            buttons.startRecording.classList.remove('d-none');
            elements.recordingStatus.classList.add('d-none');
        }
    }

    // Update recording timer
    function updateRecordingTime() {
        state.recordingTime++;
        const minutes = Math.floor(state.recordingTime / 60);
        const seconds = state.recordingTime % 60;
        elements.recordingTime.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    // Stop audio recording
    function stopRecording() {
        if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
            state.mediaRecorder.stop();
            
            // Stop all tracks on the stream
            if (state.recording) {
                state.recording.getTracks().forEach(track => track.stop());
            }
            
            // Clear timer
            clearInterval(state.recordingTimer);
            
            // Update UI
            buttons.stopRecording.classList.add('d-none');
            elements.recordingStatus.classList.add('d-none');
            elements.transcriptionLoading.classList.remove('d-none');
        }
    }

    // Reset recording state
    function resetRecording() {
        // Stop recording if active
        if (state.mediaRecorder && state.mediaRecorder.state !== 'inactive') {
            state.mediaRecorder.stop();
        }
        
        // Stop all tracks on the stream
        if (state.recording) {
            state.recording.getTracks().forEach(track => track.stop());
        }
        
        // Clear timer
        clearInterval(state.recordingTimer);
        
        // Reset state
        state.audioChunks = [];
        state.recordingTime = 0;
        
        // Update UI
        buttons.startRecording.classList.remove('d-none');
        buttons.stopRecording.classList.add('d-none');
        elements.recordingStatus.classList.add('d-none');
        elements.transcriptionLoading.classList.add('d-none');
        elements.recordingTime.textContent = '00:00';
    }

    // Process recorded audio
    function processAudio() {
        // Show loading spinner
        elements.transcriptionLoading.classList.remove('d-none');
        
        try {
            // Create a Blob from the audio chunks
            const audioBlob = new Blob(state.audioChunks, { type: 'audio/webm' });
            
            // Create a FormData object for sending the audio
            const formData = new FormData();
            formData.append('audio', audioBlob);
            formData.append('original_text', state.original_text);
            formData.append('grade_level', elements.gradeLevel.value);
            
            // Calculate audio duration (in seconds)
            state.audio_duration = state.recordingTime;
            formData.append('audio_duration', state.audio_duration);
            
            console.log('Sending audio for transcription...');
            console.log('Audio duration:', state.audio_duration);
            
            // Send the audio to the server for transcription
            fetch('/api/transcribe-audio', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    console.log('Transcription successful:', data);
                    
                    // Store the transcription result
                    state.transcription_result = data.transcription;
                    
                    // Display the transcribed text
                    elements.transcribedText.textContent = data.transcription.text || 'No text transcribed';
                    
                    // Highlight errors in the reading passage if available
                    if (data.transcription.errors && elements.readingPassageText.getAttribute('data-highlight-enabled') === 'true') {
                        highlightReadingErrors(state.original_text, data.transcription.errors);
                    }
                    
                    elements.transcriptionResult.classList.remove('d-none');
                    
                    // Enable analyze button
                    buttons.analyzeReading.disabled = false;
                    
                    showAlert('Audio transcription successful!', 'success');
                } else {
                    console.error('Transcription error:', data.error);
                    showAlert('Error processing audio: ' + (data.error || 'Unknown error'), 'danger');
                }
            })
            .catch(error => {
                console.error('Error processing audio:', error);
                showAlert('Error processing audio. Please try again.', 'danger');
            })
            .finally(() => {
                // Hide loading spinner
                elements.transcriptionLoading.classList.add('d-none');
            });
        } catch (error) {
            console.error('Error in processAudio:', error);
            showAlert('Error processing audio recording. Please try again.', 'danger');
            elements.transcriptionLoading.classList.add('d-none');
        }
    }

    // Highlight reading errors in the passage text
    function highlightReadingErrors(originalText, errors) {
        if (!errors || errors.length === 0) {
            return;
        }
        
        // Create a copy of the original text for highlighting
        let highlightedText = originalText;
        let htmlText = '';
        let lastIndex = 0;
        
        // Sort errors by position to process them in order
        errors.sort((a, b) => a.position - b.position);
        
        // Process each error and apply appropriate highlighting
        errors.forEach(error => {
            const start = error.position;
            const end = error.position + error.word.length;
            const errorWord = originalText.substring(start, end);
            
            // Add text before the error
            htmlText += originalText.substring(lastIndex, start);
            
            // Add the highlighted error based on type
            if (error.type === 'mispronounced') {
                htmlText += `<span class="error-highlight mispronounced" title="Mispronounced: ${error.correct}">${errorWord}</span>`;
            } else if (error.type === 'skipped') {
                htmlText += `<span class="error-highlight skipped" title="Skipped">${errorWord}</span>`;
            } else if (error.type === 'substituted') {
                htmlText += `<span class="error-highlight substituted" title="Said: ${error.said} instead of: ${errorWord}">${errorWord}</span>`;
            } else {
                htmlText += errorWord;
            }
            
            lastIndex = end;
        });
        
        // Add any remaining text
        htmlText += originalText.substring(lastIndex);
        
        // Update the reading passage with highlighted text
        elements.readingPassageText.innerHTML = htmlText;
        
        // Show the error highlighting legend
        const legendElement = document.querySelector('.error-highlight-legend');
        if (legendElement) {
            legendElement.classList.remove('d-none');
        }
        
        // Add CSS for the highlights if not already added
        if (!document.getElementById('highlight-styles')) {
            const style = document.createElement('style');
            style.id = 'highlight-styles';
            style.textContent = `
                .error-highlight {
                    padding: 0 2px;
                    border-radius: 3px;
                    cursor: pointer;
                }
                .error-highlight.mispronounced {
                    background-color: #fff3cd;
                    border-bottom: 2px solid #ffca2c;
                }
                .error-highlight.skipped {
                    background-color: #e2e3e5;
                    border-bottom: 2px solid #9e9e9e;
                }
                .error-highlight.substituted {
                    background-color: #f8d7da;
                    border-bottom: 2px solid #dc3545;
                }
            `;
            document.head.appendChild(style);
        }
    }

    // Analyze reading comprehensively
    function analyzeReadingComprehensive() {
        // Show loading state
        buttons.analyzeReading.disabled = true;
        buttons.analyzeReading.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Analyzing...';
        
        try {
            // Check if transcription exists
            if (!state.transcription_result) {
                showAlert('No transcription available. Please record your reading first.', 'warning');
                resetAnalyzeButtonState();
                return;
            }
            
            // Prepare request data
            const requestData = {
                original_text: state.original_text,
                transcription_result: state.transcription_result,
                grade_level: elements.gradeLevel.value,
                audio_duration: state.audio_duration,
                student_name: elements.studentName.value || 'Anonymous Student',
                passage_title: state.passage_title
            };
            
            // Include grammar evaluation if available
            if (state.grammar_evaluation) {
                requestData.grammar_evaluation = state.grammar_evaluation;
            }
            
            console.log('Sending analysis request:', requestData);
            
            // Send request to analyze the reading
            fetch('/api/analyze-comprehensive', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    console.log('Analysis successful:', data);
                    
                    // Store analysis result
                    state.analysis_result = data.analysis;
                    
                    // Display results
                    displayComprehensiveResults(data.analysis, data.highlighted_text);
                    
                    // Enable results navigation
                    navButtons.results.disabled = false;
                    
                    // Show results section
                    showSection('results');
                    
                    showAlert('Reading analysis complete!', 'success');
                } else {
                    console.error('Analysis error:', data.error);
                    showAlert('Error analyzing reading: ' + (data.error || 'Unknown error'), 'danger');
                }
            })
            .catch(error => {
                console.error('Error analyzing reading:', error);
                showAlert('Error analyzing reading. Please try again.', 'danger');
            })
            .finally(() => {
                resetAnalyzeButtonState();
            });
        } catch (error) {
            console.error('Error in analyzeReadingComprehensive:', error);
            showAlert('Error analyzing reading. Please try again.', 'danger');
            resetAnalyzeButtonState();
        }
    }

    // Reset the analyze button state
    function resetAnalyzeButtonState() {
        buttons.analyzeReading.disabled = false;
        buttons.analyzeReading.innerHTML = '<i class="fas fa-chart-bar me-2"></i> Analyze Reading';
    }

    // Display comprehensive analysis results
    function displayComprehensiveResults(analysis, highlightedText) {
        // Overview tab
        document.getElementById('overall-score').textContent = analysis.combined_literacy_score || analysis.accuracy_percentage;
        document.getElementById('reading-level').textContent = analysis.reading_level;
        document.getElementById('grade-equivalent').textContent = analysis.grade_equivalent;
        
        // Strengths list
        const strengthsList = document.getElementById('strengths-list');
        strengthsList.innerHTML = '';
        
        analysis.strengths.forEach(strength => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = strength;
            strengthsList.appendChild(li);
        });
        
        // Areas to improve list
        const areasList = document.getElementById('areas-list');
        areasList.innerHTML = '';
        
        analysis.areas_to_improve.forEach(area => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = area;
            areasList.appendChild(li);
        });
        
        // Next steps list
        const nextStepsList = document.getElementById('next-steps-list');
        nextStepsList.innerHTML = '';
        
        analysis.next_steps.forEach(step => {
            const li = document.createElement('li');
            li.className = 'list-group-item';
            li.textContent = step;
            nextStepsList.appendChild(li);
        });
        
        // Reading analysis tab
        document.getElementById('accuracy-score').textContent = `${Math.round(analysis.accuracy_percentage)}%`;
        document.getElementById('fluency-score').textContent = Math.round(analysis.fluency_metrics.fluency_level.score);
        document.getElementById('wpm-score').textContent = Math.round(analysis.fluency_metrics.words_per_minute);
        document.getElementById('comprehension-score').textContent = `${Math.round(analysis.comprehension_estimate)}%`;
        
        // Highlighted text
        document.getElementById('highlighted-text').innerHTML = highlightedText;
        
        // Fluency metrics table
        document.getElementById('wpm-value').textContent = Math.round(analysis.fluency_metrics.words_per_minute);
        document.getElementById('target-wpm').textContent = analysis.fluency_metrics.benchmark.wpm_target;
        document.getElementById('fluency-level').textContent = analysis.fluency_metrics.fluency_level.level;
        document.getElementById('prosody-score').textContent = `${Math.round(analysis.prosody_score)}/100`;
        
        // Word statistics chart
        createWordStatsChart(analysis.word_statistics);
        
        // Grammar results tab (if available)
        if (analysis.grammar_score !== undefined) {
            document.getElementById('grammar-result-score').textContent = `${analysis.grammar_score}%`;
            document.getElementById('grammar-result-level').textContent = analysis.grammar_proficiency;
            document.getElementById('grammar-result-correct').textContent = `${state.grammar_evaluation.correct_count}/${state.grammar_evaluation.total_questions}`;
            
            // Concepts lists
            const conceptsMastered = document.getElementById('concepts-mastered-result');
            const conceptsImprove = document.getElementById('concepts-improve-result');
            const recommendations = document.getElementById('grammar-recommendations-result');
            
            conceptsMastered.innerHTML = '';
            conceptsImprove.innerHTML = '';
            recommendations.innerHTML = '';
            
            state.grammar_evaluation.concepts_mastered.forEach(concept => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                li.textContent = formatConceptName(concept);
                conceptsMastered.appendChild(li);
            });
            
            state.grammar_evaluation.concepts_to_improve.forEach(concept => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                li.textContent = formatConceptName(concept);
                conceptsImprove.appendChild(li);
            });
            
            state.grammar_evaluation.recommendations.forEach(recommendation => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                li.textContent = recommendation;
                recommendations.appendChild(li);
            });
        }
        
        // Recommendations tab
        const readingTopicsContainer = document.getElementById('reading-topics-container');
        readingTopicsContainer.innerHTML = '';
        
        if (state.grammar_evaluation && state.grammar_evaluation.suggested_reading_topics) {
            state.grammar_evaluation.suggested_reading_topics.forEach(topic => {
                const topicCard = document.createElement('div');
                topicCard.className = 'col-md-6 mb-3';
                
                const difficultyBadgeClass = {
                    'easy': 'bg-success',
                    'medium': 'bg-warning',
                    'challenging': 'bg-danger'
                }[topic.difficulty] || 'bg-secondary';
                
                const focusBadgeClass = {
                    'narrative': 'bg-primary',
                    'informational': 'bg-info',
                    'dialogue': 'bg-secondary',
                    'time shifts': 'bg-dark'
                }[topic.focus] || 'bg-secondary';
                
                topicCard.innerHTML = `
                    <div class="card reading-topic-card">
                        <div class="card-header bg-light">
                            <span class="badge ${difficultyBadgeClass}">${topic.difficulty.charAt(0).toUpperCase() + topic.difficulty.slice(1)}</span>
                            <span class="badge ${focusBadgeClass}">${topic.focus.charAt(0).toUpperCase() + topic.focus.slice(1)}</span>
                            <span class="badge bg-secondary">${topic.word_count} words</span>
                        </div>
                        <div class="card-body">
                            <h6 class="card-title">${topic.title}</h6>
                            <p class="card-text">${topic.description}</p>
                        </div>
                    </div>
                `;
                
                readingTopicsContainer.appendChild(topicCard);
            });
        }
        
        // Personalized next steps
        const nextStepsDetailed = document.getElementById('next-steps-detailed');
        nextStepsDetailed.innerHTML = '';
        
        analysis.next_steps.forEach(step => {
            const li = document.createElement('li');
            li.className = 'mb-2';
            li.textContent = step;
            nextStepsDetailed.appendChild(li);
        });
    }

    // Create word statistics chart
    function createWordStatsChart(wordStats) {
        const ctx = document.getElementById('word-stats-chart').getContext('2d');
        
        // Destroy existing chart if it exists
        if (window.wordStatsChart) {
            window.wordStatsChart.destroy();
        }
        
        // Create new chart
        window.wordStatsChart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['Correct', 'Mispronounced', 'Skipped', 'Substituted'],
                datasets: [{
                    data: [
                        wordStats.correct,
                        wordStats.mispronounced,
                        wordStats.skipped,
                        wordStats.substituted
                    ],
                    backgroundColor: [
                        '#4caf50',  // Correct - green
                        '#ffeb3b',  // Mispronounced - yellow
                        '#9e9e9e',  // Skipped - gray
                        '#f44336'   // Substituted - red
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'right',
                    }
                }
            }
        });
    }

    // Reset the assessment
    function resetAssessment() {
        // Reset state
        state.original_text = '';
        state.passage_title = '';
        state.spoken_text = '';
        state.transcription_result = null;
        state.recording = null;
        state.audio_duration = 0;
        state.grammar_test = null;
        state.grammar_evaluation = null;
        state.analysis_result = null;
        
        // Reset UI
        elements.previewCard.classList.add('d-none');
        elements.previewTitle.textContent = '';
        elements.previewText.textContent = '';
        
        resetRecording();
        
        // Reset forms
        forms.uploadForm.reset();
        forms.textForm.reset();
        
        // Disable results navigation
        navButtons.results.disabled = true;
        
        // Show text input section
        showSection('textInput');
        
        showAlert('Assessment reset. Ready for a new assessment.', 'info');
    }

    // Initialize the application
    init();
});